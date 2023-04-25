var m = require("mithril")
var CalibrationMethod = require("../models/CalibrationMethod")

module.exports = {
  oninit: CalibrationMethod.loadList,
  view: function(vnode) {
    return m("select", {
        style: "width: 100%;",
        onchange: (event) => {
          const cm = CalibrationMethod.list.get(event.target.value)
          // XXX: I don't understand why, but vnode.attrs.component (set to "this" in CalibrationView) seems
          //      seems to be a CalibrationView whose prototype is the original CalibrationView.
          if (cm !== undefined) {
            Object.getPrototypeOf(vnode.attrs.component).selected = cm
            Object.getPrototypeOf(vnode.attrs.component).params.clear()
            cm.properties.inputs.forEach((input) => {
              Object.getPrototypeOf(vnode.attrs.component).params.set(input, null)
            })
          } else {
            Object.getPrototypeOf(vnode.attrs.component).selected = null
          }
        }
      },
      [m("option", {value: 0}, "-- not in use --")].concat(Array.from(CalibrationMethod.list, ([key, value]) => {
        return m("option", {value: key}, value.name)
      }))
    )
  },
}
