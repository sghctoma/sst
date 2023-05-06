var m = require("mithril")

var Setup = {
  list: new Map(),
  loadList: function() {
    return m.request({
      method: "GET",
      url: "/api/setup",
    })
    .then(function(result) {
      result.forEach(item => {Setup.list.set(item.id, item)})
    })
  },
  putCombined: function(combined) {
    return m.request({
      method: "PUT",
      url: "/api/setup/combined",
      headers: {
        "X-CSRF-TOKEN": SST.getCookie("csrf_access_token"),
      },
      body: combined,
    })
    .then(function(result) {
      return result.id
    })
  },
}

module.exports = Setup

