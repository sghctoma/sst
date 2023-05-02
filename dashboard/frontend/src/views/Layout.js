var m = require("mithril")
var Session = require("../models/Session")
var SessionList = require("./SessionList")
var Login = require("./Login.js")
var Dialog = require("./Dialog")
var SetupWizard = require("./SetupWizard")

var timestampToString = function(timestamp) {
  return new Date(timestamp * 1e3).toLocaleString("hu-HU", {
    timeZone: "UTC",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })
}

var Layout = {
  oninit: function(vnode) {
    Layout.setupDialog = new Dialog()
    Layout.loginDialog = new Dialog()
  },
  view: function(vnode) {
    return m("main.layout", [
      m("input.drawer-toggle", {type: "checkbox", id: "drawer-toggle"}),
      m("label.drawer-toggle-label", {for: "drawer-toggle", id: "drawer-toggle-label"}),
      m("header", [
        m(".sst-title", {onclick: Layout.loginDialog.state.openDialog}, "sufni suspension telemetry"),
        Session.current.loaded ? m("div", [
          m("span", {id: "sname"}, Session.current.name),
          " (" + timestampToString(Session.current.start_time) + " UTC)",
        ]) : null,
      ]),
      m("nav.drawer", {id: "drawer"}, [
        Session.current.full_access ? m("div", {style: "margin-bottom: 15px;"}, [
          m("h4", "Manage"),
          m("div", {
              style: "display: inline-block;",
              class: "route-link",
              onclick: Layout.setupDialog.state.openDialog,
            }, "Create new bike setup"),
        ]) : null,
        m("div", {style: "margin-bottom: 15px;"}, [
          m("h4", "Sessions"),
          m(SessionList)
        ]),
      ]),
      m(Layout.loginDialog, {
        top: "40px",
        left: "200px",
        onopen: null,
        onclose: null,
      }, m(Login)),
      Session.current.full_access ? m(Layout.setupDialog, {
        top: "100px",
        left: "80px",
        onopen: SetupWizard.onopen,
        onclose: SetupWizard.onclose,
      }, m(SetupWizard, {parentDialog: Layout.setupDialog})) : null,
      vnode.children,
    ])
  }
}

module.exports = Layout
