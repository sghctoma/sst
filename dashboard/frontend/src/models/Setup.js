var m = require("mithril")

var Setup = {
  list: new Map(),
  loadList: function() {
    return m.request({
      method: "GET",
      url: "/api/setup",
      withCredentials: true,
    })
    .then(function(result) {
      result.forEach(item => {Setup.list.set(item.id, item)})
    })
  },
  put: function(setup) {
    return m.request({
      method: "PUT",
      url: "/api/setup",
      headers: {
        "X-CSRF-TOKEN": SST.getCookie("csrf_access_token"),
      },
      withCredentials: true,
      body: setup
    })
    .then(function(result) {
      return result.id
    })
  },
}

module.exports = Setup

