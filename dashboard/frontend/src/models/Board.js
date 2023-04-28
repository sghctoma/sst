var m = require("mithril")

var Board = {
  list: new Map(),
  loadList: function() {
    return m.request({
      method: "GET",
      url: "/api/board",
      headers: {
        "X-CSRF-TOKEN": SST.getCookie("csrf_access_token"),
      },
      withCredentials: true,
    })
    .then(function(result) {
      result.forEach(item => {Board.list.set(item.id, item)})
    })
  },
}

module.exports = Board
