var m = require("mithril")
var Session = require("../models/Session")
var SessionList = require("./SessionList")

module.exports = {
  view: function(vnode) {
    return m("main.layout", [
      m("input.drawer-toggle", {type: "checkbox", id: "drawer-toggle"}),
      m("label.drawer-toggle-label", {for: "drawer-toggle", id: "drawer-toggle-label"}),
      m("header", [
        "sufni suspension telemetry",
        m("div", {style: "float: right;"}, [
          m("span", {id: "sname"}, Session.current.name),
          " (" + Session.current.start_time + " UTC)",
        ]),
      ]),
      m("nav.drawer", {id: "drawer"}, [m("h4", "Sessions"), m(SessionList)]),
      vnode.children,
    ])
  }
}
