var m = require("mithril")
var Board = require("../models/Board")

module.exports = {
  oninit: Board.loadList,
  view: function(vnode) {
    return m(".board-list", [
      m("input", {
        type: "text",
        style: "width: 100%;",
        list: "boards",
        value: vnode.attrs.selected,
        oninput: (event) => {
          vnode.attrs.onselect(event.target.value);
        },
      }),
      m("datalist", {id: "boards"},
        Array.from(Board.list, ([key, value]) => {
          return m("option", key)
        }),
      )
    ])
  },
}

