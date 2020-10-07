# -*- coding: utf-8 -*-
__all__ = ["MultiAxisPlotWidget"]

import weakref

from ..functions import mkBrush, mkPen
from ..graphicsItems.AxisItem import AxisItem
from ..graphicsItems.PlotDataItem import PlotDataItem
from ..graphicsItems.PlotItem.PlotItem import PlotItem
from ..graphicsItems.ViewBox import ViewBox
from ..Qt import QtCore
from ..widgets.PlotWidget import PlotWidget


class MultiAxisPlotWidget(PlotWidget):
    # TODO: propagate mouse events of master viewbox, to children
    # TODO: axis specific menu options for axis, propagate to linked children

    def __init__(self, **kargs):
        """PlotWidget but with support for multi axis"""
        PlotWidget.__init__(self, **kargs)
        # plotitem shortcut
        self.pi = super().getPlotItem()
        # default vb from plotItem
        self.vb = self.pi.getViewBox()
        # layout shortcut
        self.layout = self.pi.layout
        # hide default axis
        for a in ["left", "bottom", "right", "top"]:
            self.pi.hideAxis(a)
        # CHARTS
        self.axis = {}
        self.charts = {}
        self.axis_connections = {}

    def addAxis(self, name, position, label=None, units=None, **kwargs):
        axis = AxisItem(position, **kwargs)
        axis.setLabel(label, units)
        self.axis[name] = axis
        self.axis_connections[name] = []

    def addChart(self, name, x_axis=None, y_axis=None, set_color=False, show_grid=False, **kwargs):
        # CHART
        color = self.colors[len(self.charts)]
        # ACTUAL XY GRAPH
        chart = PlotDataItem(
            connect="all",
            # symbol="+",
            symbol=None,
            pen=mkPen(
                color=color,
                width=2,
                s=QtCore.Qt.SolidLine,
                # brush=brush,
                c=QtCore.Qt.RoundCap,
                j=QtCore.Qt.RoundJoin
            ),
            # brush=mkBrush(
            #     color=color,
            #     bs=QtCore.Qt.SolidPattern,
            # ),
            downsampleMethod="peak",
            autoDownsample=True,
            clipToView=True
        )
        if x_axis is None and y_axis is None:
            # use default plotitem if none provided
            plotitem = self.pi
        else:
            # Create and place axis items if necessary
            # X AXIS
            if x_axis is None:  # use default axis if none provided
                x_axis = "bottom"
            if x_axis in self.axis:
                x = self.axis[x_axis]
            else:
                self.addAxis(x_axis, "bottom", parent=plotitem)
                x = self.axis[x_axis]
            # Y AXIS
            if y_axis is None:  # use default axis if none provided
                y_axis = "left"
            if y_axis in self.axis:
                y = self.axis[y_axis]
            else:
                self.addAxis(y_axis, "left", parent=plotitem)
                y = self.axis[y_axis]
            # VIEW
            plotitem = PlotItem(parent=self.pi, name=name, **kwargs)
            # hide all plotitem axis (they vould interfere with viewbox)
            for a in ["left", "bottom", "right", "top"]:
                plotitem.hideAxis(a)
            # link axis to view
            view = plotitem.getViewBox()
            self.linkAxisToView(x_axis, view)
            self.linkAxisToView(y_axis, view)
            for k, pos, axis in [["top", [1, 1], y], ["bottom", [3, 1], x]]:  # , ["left", [2, 0], y], ["right", [2, 2], x]]:
                # # DO NOT USE, WILL MAKE AXIS UNMATCHED TO DATA
                # # you can't add the new ones after, it doesn't work for some reason
                # # hide them instead
                # plotitem.layout.removeItem(plotitem.layout.itemAt(*pos))
                plotitem.axes[k] = {"item": axis, "pos": pos}
            # fix parent legend not showing child charts
            plotitem.legend = self.pi.legend
            # resize plotitem according to the master one
            # resizing it's view doesn't work for some reason
            self.vb.sigResized.connect(lambda vb: plotitem.setGeometry(vb.sceneBoundingRect()))
        if set_color:
            # match y axis color
            y.setPen(mkPen(color=color))
        if show_grid is not False:
            if show_grid is True:
                x.setGrid(int(0.3 * 255))
                y.setGrid(int(0.3 * 255))
            else:
                if "x" in show_grid and show_grid["x"] is not False:
                    x.setGrid(int(show_grid["x"] * 255))
                if "y" in show_grid and show_grid["y"] is not False:
                    y.setGrid(int(show_grid["y"] * 255))
        plotitem.addItem(chart)
        # keep plotitem inside chart
        chart.plotItem = plotitem
        # keep axis track
        chart.axis = [x_axis, y_axis]
        # keep chart
        self.charts[name] = chart
        # create a mapping for this chart and his axis
        self.axis_connections[x_axis].append(name)
        self.axis_connections[y_axis].append(name)
        # data keep for the chart to add support for adding data
        self.parsed_data[name] = []

    def clearLayout(self):
        while self.layout.count() > 0:
            item = self.layout.itemAt(0)
            self.layout.removeAt(0)
            self.scene().removeItem(item)
            del item
        # clear plotItem
        self.pi.clear()

    def linkAxisToView(self, axis_name, view):
        axis = self.axis[axis_name]
        # connect view changes to axis
        # FROM AxisItem.linkToView
        if axis.orientation in ["right", "left"]:
            view.sigYRangeChanged.connect(axis.linkedViewChanged)
        elif axis.orientation in ["top", "bottom"]:
            view.sigXRangeChanged.connect(axis.linkedViewChanged)
        view.sigResized.connect(axis.linkedViewChanged)
        if axis.linkedView() is None:
            axis._linkedView = weakref.ref(view)
        # set axis main view link if not assigned
        axis_view = axis.linkedView()
        if axis_view is not view:
            # FROM ViewBox.linkView
            # connext axis's view changes to view since axis acts just like a proxy to it
            if axis.orientation in ["right", "left"]:
                axis_view.sigYRangeChanged.connect(lambda v: view.linkedViewChanged(v, ViewBox.YAxis))
                axis_view.sigResized.connect(lambda v: view.linkedViewChanged(v, ViewBox.YAxis))
                axis_view.sigYRangeChangedManually.connect(lambda mask: self.disableAxisAutoRange(axis_name))
            elif axis.orientation in ["top", "bottom"]:
                axis_view.sigXRangeChanged.connect(lambda v: view.linkedViewChanged(v, ViewBox.XAxis))
                axis_view.sigResized.connect(lambda v: view.linkedViewChanged(v, ViewBox.XAxis))
                axis_view.sigXRangeChangedManually.connect(lambda mask: self.disableAxisAutoRange(axis_name))
            # disable autorange on manual movements

    def makeLayout(self, axis=None, charts=None):
        self.clearLayout()
        # SELECT AND ASSEMBLE AXIS
        if axis is None:
            axis = list(self.axis)
        lo = {
            "left": [],
            "right": [],
            "top": [],
            "bottom": [],
        }
        for k, a in self.axis.items():
            if k in axis:
                lo[a.orientation].append(a)
        vx = len(lo["left"])
        vy = 1 + len(lo["top"])
        # ADD TITLE ON TOP
        self.pi.titleLabel.show()
        self.layout.addItem(self.pi.titleLabel, 0, vx)
        # ADD MAIN PLOTITEM
        self.vb.show()
        self.layout.addItem(self.vb, vy, vx)
        # ADD AXIS
        for x, a in enumerate(lo["left"] + [None] + lo["right"]):
            if a is not None:
                a.show()
                self.layout.addItem(a, vy, x)
        for y, a in enumerate(lo["top"] + [None] + lo["bottom"]):
            if a is not None:
                a.show()
                self.layout.addItem(a, y + 1, vx)
        # SELECT CHARTS
        if charts is None:
            charts = list(self.charts)
        for k, c in self.charts.items():
            if k in charts:
                c.show()
            else:
                c.hide()
        # MOVE LEGEND TO LAYOUT
        if self.pi.legend is not None:
            self.pi.legend.setParentItem(self.pi)

    def clean(self):
        # CLEAR PLOTS
        for p in self.charts.values():
            p.clear()

    def getPlotItem(self, name=None):
        if name is None:
            return self.pi
        else:
            return self.charts[name].plotItem

    def setAxisRange(self, axis, range=None, **kwargs):
        if range is None or len(range) == 0:
            # AUTORANGE
            range = None
        elif len(range) == 1:
            # ZERO TO R
            range = [min(0, *range), max(0, *range)]
        elif len(range) == 2:
            # SET GIVEN RANGE
            range = [min(*range), max(*range)]
        else:
            raise AttributeError("bad range")
        if range is None:
            self.enableAxisAutoRange(axis)
        else:
            self.disableAxisAutoRange(axis)
            a = self.axis[axis]
            vb = a.linkedView()
            if a.orientation in ["top", "bottom"]:  # IS X AXIS
                vb.getViewBox().setXRange(*range, **kwargs)
            elif a.orientation in ["left", "right"]:  # IS Y AXIS
                vb.setYRange(*range, **kwargs)

    def update(self):
        for axis_name, connections in self.axis_connections.items():
            axis = self.axis[axis_name]
            if axis.autorange:
                charts = [self.charts[connection] for connection in connections]
                bounds = []
                if axis.orientation in ["top", "bottom"]:  # IS X AXIS
                    for chart in charts:
                        bounds += chart.dataBounds(ViewBox.XAxis)
                    bounds = [bound for bound in bounds if bound is not None]
                    if len(bounds) > 0:
                        for chart in charts:
                            chart.plotItem.getViewBox().setXRange(min(bounds), max(bounds))
                elif axis.orientation in ["left", "right"]:  # IS Y AXIS
                    for chart in charts:
                        bounds += chart.dataBounds(ViewBox.YAxis)
                    bounds = [bound for bound in bounds if bound is not None]
                    if len(bounds) > 0:
                        for chart in charts:
                            chart.plotItem.getViewBox().setYRange(min(bounds), max(bounds))

    def enableAxisAutoRange(self, axis_name):
        self.axis[axis_name].autorange = True

    def disableAxisAutoRange(self, axis_name):
        self.axis[axis_name].autorange = False
