var m = require("mithril")

var Calibration = {
  list: new Map(),
  loadList: function() {
    return m.request({
      method: "GET",
      url: "/api/calibration",
      withCredentials: true,
    })
    .then(function(result) {
      result.forEach(item => {Calibration.list.set(item.id, item)})
    })
  },
  put: function(calibration) {
    return m.request({
      method: "PUT",
      url: "/api/calibration",
      headers: {
        "X-CSRF-TOKEN": SST.getCookie("csrf_access_token"),
      },
      withCredentials: true,
      body: calibration
    })
    .then(function(result) {
      return result.id
    })
  },
}

module.exports = Calibration
