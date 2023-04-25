var m = require("mithril")
var Session = require("../models/Session")
var SessionList = require("./SessionList")
var Login = require("./Login.js")
var Dialog = require("./Dialog")
var SetupWizard = require("./SetupWizard")

module.exports = {
  view: function(vnode) {
    return m("main.layout", [
      m("input.drawer-toggle", {type: "checkbox", id: "drawer-toggle"}),
      m("label.drawer-toggle-label", {for: "drawer-toggle", id: "drawer-toggle-label"}),
      m("header", [
        "sufni suspension telemetry",
        Session.current.loaded ? m("div", {style: "float: right;"}, [
          m("span", {id: "sname"}, Session.current.name),
          " (" + Session.current.start_time + " UTC)",
        ]) : null,
      ]),
      m("nav.drawer", {id: "drawer"}, [
        m("div", {style: "margin-bottom: 15px;"}, [
          m("h4", "User"),
          m(Login),
        ]),
        m("div", {style: "margin-bottom: 15px;"}, [
          m("h4", "Manage"),
          m("div", {
              style: "display: inline-block;",
              class: "route-link",
              onclick: Dialog.state.openDialog,
            }, "Create new bike setup"),
        ]),
        m("div", {style: "margin-bottom: 15px;"}, [
          m("h4", "Sessions"),
          m(SessionList)
        ]),
      ]),
      m(Dialog, {}, m(SetupWizard)),
      vnode.children,
    ])
  }
}
