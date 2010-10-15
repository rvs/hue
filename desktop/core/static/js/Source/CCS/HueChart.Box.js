/*
---

script: HueChart.Box.js

description: Defines HueChart.Box, which builds on HueChart and serves as a base class to build charts which are rectangular in nature, having x and y axes.

license: MIT-style license

authors:
- Marcus McLaughlin

requires:
- protovis/Protovis
- More/Date
- Core/Events
- Core/Options
- ccs-shared/Number.Files
- ccs-shared/HueChart

provides: [ HueChart.Box ]

...
*/

//Contains functionality useful for charts which are rectangular.
HueChart.Box = new Class({

        Extends: HueChart,

        /* options:series: the array of data series which are found in the chart data,
                xField: the field in the data table which should be used as the xAxis label, and for determining where points are on the xAxis
                xDate: is the xField a date ?
                positionIndicator: should the position indicator be shown ?
                ticks: should tick marks be shown ?
                lables: should axis labels be shown ?
                onPointMouseOut: function that should be run when the mouse is moved out of the chart
                onPointMouseOver: function that should be run when the mouse is moved over a datapoint, takes the dataPoint as an argument
        */

        initialize: function(element, options) {
                this.parent(element, options);
                this.selected_index = -1;
                if(this.options.xDate) {
                        //If the xField is a date property, prepare the dates for sorting
                        //Change the xField to the new property designed for sorting dates
                        this.data.prepareDates(this.options.xField);
                        this.options.xField = 'seconds_from_first';
                } else {
                        //Otherwise sort by the x property.
                        this.data.sortByProperty(this.options.xField);
                }
                this.addEvent('setupChart', function(vis) {
                        this.setScales(vis);
                        this.addGraph(vis);
                        if (this.options.ticks) this.setTicks(vis);
                        if (this.options.labels) this.setLabels(vis);
                        if (this.options.positionIndicator) this.setPositionIndicator(vis);
                        if (this.$events.pointMouseOut && this.$events.pointMouseOver) this.addEventBar(vis);
                }.bind(this));
        },
        
        //Set the scales which will be used to convert data values into positions for graph objects
        setScales: function(vis) {
                //Get the minimum and maximum x values.
                var xMin = this.data.getMinValue(this.options.xField);
                var xMax = this.data.getMaxValue(this.options.xField);
                //Get the maximum of the values that are to be graphed
                var maxValue = this.data.getMaxValue(this.options.series);
                this.xScale = pv.Scale.linear(xMin, xMax).range(this.options.leftPadding, this.width - this.options.rightPadding);
                this.yScale = pv.Scale.linear(0, maxValue * 1.2).range(this.options.bottomPadding, (this.height - (this.options.topPadding)));
        },
        
        //Draw the X and Y tick marks.
        setTicks:function(vis) {
                //Add X-Ticks.
                //Create tick array.
                var xTicks = (this.options.xDate ? this.data.createTickArray(7, 'day') : this.xScale.ticks(7));
                //Create rules (lines intended to denote scale)
                vis.add(pv.Rule)
                        //Use the tick array as data.
                        .data(xTicks)
                        //The bottom of the rule should be at the bottomPadding - the height of the rule.  
                        .bottom(this.options.bottomPadding - this.options.xTickHeight)
                        //The left of the rule should be at the data object's xField value scaled to pixels.
                        .left(function(d) { return this.xScale(d[this.options.xField]); }.bind(this))
                        //Set the height of the rule to the xTickHeight
                        .height(this.options.xTickHeight)
                        .strokeStyle("#555")
                        //Add label to bottom of each rule
                        .anchor("bottom").add(pv.Label)
                                .text(function(d) {
                                        //If the option is a date, format the date property field.
                                        //Otherwise, simply show it.
                                        if(this.options.xDate) {
                                                return d.sample_date.format("%b %d");
                                        } else {
                                                return d[this.options.xField];
                                        }
                                }.bind(this));
               
                //Add Y-Ticks
                //Calculate number of yTicks to show.
                //Approximate goal of 35 pixels between yTicks.
                var yTickCount = (this.height - (this.options.bottomPadding + this.options.topPadding))/35;
                var tickScale = this.yScaleTicks || this.yScale;
                //Create rules
                vis.add(pv.Rule)
                        //Always show at least two ticks.
                        //tickScale.ticks returns an array of values which are evenly spaced to be used as tick marks.
                        .data(tickScale.ticks(yTickCount > 1 ? yTickCount : 2))
                        //The left side of the rule should be at leftPadding pixels.
                        .left(this.options.leftPadding)
                        //The bottom of the rule should be at the tickScale.ticks value scaled to pixels.
                        .bottom(function(d) {return tickScale(d);}.bind(this))
                        //The width of the rule should be the width minuis the hoizontal padding.
                        .width(this.width - this.options.leftPadding - this.options.rightPadding + 1)
                        .strokeStyle("#555")
                        //Add label to the left which shows the number of bytes.
                        .anchor("left").add(pv.Label)
                                .text(function(d) { 
                                        if(this.options.yField == 'bytes') return d.convertFileSize(); 
                                        return d;
                                }.bind(this));
        },
        
        //Add X and Y axis labels.
        setLabels: function(vis) {
                //Add Y-Label to center of chart. 
                vis.anchor("center").add(pv.Label)
                        .textAngle(-Math.PI/2)
                        .text(function() {
                                return this.options.yField.replace("_", " ").capitalize();
                        }.bind(this))
                        .font(this.options.labelFont)
                        .left(12);
                
                //Add X-Label to center of chart.
                vis.anchor("bottom").add(pv.Label)
                        .text("Date")
                        .font(this.options.labelFont)
                        .bottom(0);
        },

        //Add a bar which indicates the position which is currently selected on the bar graph.
        setPositionIndicator: function(vis) {
                //Put selected_index in scope.
                get_selected_index = this.getSelectedIndex.bind(this);
                //Add a thin black bar which is approximately the height of the graphing area for each item on the graph.
                vis.add(pv.Bar)
                        .data(this.data.pureArray())
                        .left(function(d) { 
                                return this.xScale(d[this.options.xField]); 
                        }.bind(this))
                        .height(this.height - (this.options.bottomPadding + this.options.topPadding))
                        .bottom(this.options.bottomPadding)
                        .width(2)
                        //Show bar if its index is selected, otherwise hide it.
                        .fillStyle(function() {
                                if(this.index == get_selected_index()) return "black";
                                else return null;
                        });
        },
        
        //Add bar detecting mouse events.
        addEventBar: function(vis) {
                //Create functions which handle the graph specific aspects of the event and call the event arguments.
                var outVisFn = function() {
                        this.selected_index = -1;
                        this.fireEvent('pointMouseOut');
                        return vis;
                }.bind(this);
                var moveVisFn = function() {
                        //Convert the mouse's xValue into its corresponding data value on the xScale. 
                        var mx = this.xScale.invert(vis.mouse().x);
                        //Search the data for the index of the element at this data value.
                        i = pv.search(this.data.pureArray().map(function(d){ return d[this.options.xField]; }.bind(this)), Math.round(mx));
                        //Adjust for ProtoVis search
                        i = i < 0 ? (-i - 2) : i;
                        //Set selected index and run moveFn if the item exists
                        if(i >= 0 && i < this.data.getLength()) {
                                this.selected_index = i;
                                this.fireEvent('pointMouseOver', this.data.pureArray()[this.selected_index]);
                        }
                        return vis;
                }.bind(this);
                vis.add(pv.Bar)
                        .fillStyle("rgba(0,0,0,.001)")
                        .event("mouseout", outVisFn)
                        .event("mousemove", moveVisFn);
        }
        
});


