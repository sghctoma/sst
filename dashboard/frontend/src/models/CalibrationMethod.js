var m = require("mithril")

var CalibrationMethod = {
  list: new Map(),
  loadList: function() {
    return m.request({
      method: "GET",
      url: "/api/calibration-method",
    })
    .then(function(result) {
      result.forEach(item => {CalibrationMethod.list.set(item.id.toString(), item)})
    })
  },
}

module.exports = CalibrationMethod
