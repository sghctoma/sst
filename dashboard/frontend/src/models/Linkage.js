var m = require("mithril")

var Linkage = {
  list: new Map(),
  loadList: function() {
    return m.request({
      method: "GET",
      url: "/api/linkage",
    })
    .then(function(result) {
      result.forEach(item => {Linkage.list.set(item.id.toString(), item)})
    })
  },
}

module.exports = Linkage

