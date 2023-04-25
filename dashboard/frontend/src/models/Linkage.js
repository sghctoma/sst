var m = require("mithril")

var Linkage = {
  list: new Map(),
  loadList: function() {
    return m.request({
      method: "GET",
      url: "/api/linkage",
      withCredentials: true,
    })
    .then(function(result) {
      result.forEach(item => {Linkage.list.set(item.id, item)})
    })
  },
  put: function(linkage) {
    return m.request({
      method: "PUT",
      url: "/api/linkage",
      headers: {
        "X-CSRF-TOKEN": SST.getCookie("csrf_access_token"),
      },
      withCredentials: true,
      body: linkage
    })
    .then(function(result) {
      return result.id
    })
  },
}

module.exports = Linkage
