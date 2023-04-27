var m = require("mithril")
var CalibrationMethod = require("../models/CalibrationMethod")

module.exports = {
  oninit: CalibrationMethod.loadList,
  view: function(vnode) {
    return m("select", {
      style: "width: 100%;",
      value: vnode.attrs.selected,
      onchange: (event) => {
        vnode.attrs.onselect(event.target.value);
      }},
      [m("option", {value: 0}, "-- not in use --")].concat(Array.from(CalibrationMethod.list, ([key, value]) => {
        return m("option", {value: key}, value.name)
      }))
    )
  },
}
