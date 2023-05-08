var m = require("mithril")
var Linkage = require("../models/Linkage")

module.exports = {
  oninit: Linkage.loadList,
  view: function(vnode) {
    return m("select", {
      style: "width: 100%;",
      value: vnode.attrs.selected,
      onchange: (event) => {
        vnode.attrs.onselect(event.target.value);
      }},
      [m("option", {value: 0}, "-- create new --")].concat(Array.from(Linkage.list, ([key, value]) => {
        return m("option", {value: key}, value.name)
      }))
    )
  },
}

