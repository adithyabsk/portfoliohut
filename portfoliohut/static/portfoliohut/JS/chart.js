window.onload = function () {
    var dataPoints = [];
    var stockChart = new CanvasJS.StockChart("stockChartContainer", {
      exportEnabled: true,
      title: {
        text:"Portfolio Returns"
      },
      subtitles: [{
        text:""
      }],
      charts: [{
        axisX: {
          crosshair: {
            enabled: true,
            snapToDataPoint: true,
            valueFormatString: "MMM YYYY"
          }
        },
        axisY: {
          title: "Return percentage",
          prefix: "",
          suffix: "%",
          crosshair: {
            enabled: true,
            snapToDataPoint: true,
            valueFormatString: "$#,###.00M",
          }
        },
        data: [{
          type: "line",
          xValueFormatString: "MMM YYYY",
          yValueFormatString: "$#,###.##M",
          dataPoints : dataPoints
        }]
      }],
      
    });
  
  d3.csv("./data/transactions - transactions.csv", function(data) {
      for (var i = 0; i < data.length; i++) {
          dataPoints.push({x: new Date(data[i].DATE), y: Number(data[i].Returns)});
          console.log(data[i].DATE);
          console.log(data[i].Returns);
      }
      stockChart.render();
  
  });
  }
  