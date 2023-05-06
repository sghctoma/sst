var m = require("mithril")
var Session = require("../models/Session")
var SessionList = require("./SessionList")
var Login = require("./Login.js")
var Dialog = require("./Dialog")
var SetupWizard = require("./SetupWizard")
var VideoPlayer = require("./VideoPlayer")

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

var ErrorPopup = {
  view: function(vnode) {
    return m(".error-message", Layout.error)
  },
}

var Layout = {
  oninit: function(vnode) {
    Layout.setupDialog = new Dialog()
    Layout.loginDialog = new Dialog()
    Layout.errorDialog = new Dialog()
    Layout.error = ""
  },
  setError: function(error) {
    Layout.error = error
    if (error) {
      Layout.errorDialog.state.openDialog()
      m.redraw()
    }
  },
  view: function(vnode) {
    return m("main.layout", [
      m("input.drawer-toggle", {type: "checkbox", id: "drawer-toggle"}),
      m("label.drawer-toggle-label", {for: "drawer-toggle", id: "drawer-toggle-label"}),
      m("header", [
        m(".sst-title", "sufni suspension telemetry"),
        Session.current.loaded ? m("div", [
          m("span", {id: "sname"}, Session.current.name),
          " (" + timestampToString(Session.current.start_time) + " UTC)",
        ]) : null,
        m(".toolbar", [
          Session.current.full_access ? m("span.fa-solid fa-gear toolbar-icon", {
            onclick: Layout.setupDialog.state.openDialog,
          }) : null,
          Session.current.full_access ? m("input[type=file][id=gpx-input]", {
            accept: ".gpx",
            onchange: (event) => {
              Session.importGPX(event)
              .catch((error) => {
                if (error.code == 401) {
                  Login.logout()
                } else {
                  setTimeout(() => {
                    Session.gpxError = ""
                    m.redraw()
                  }, 1500)
                }
              })
            },
          }) : null,
          Session.current.full_access ?
            (!Session.gpxError ? m("label.fa-solid fa-map-location-dot toolbar-icon", {for: "gpx-input"}) :
                                m("span.fa-solid fa-ban toolbar-icon input-error")) :
          null,
          m("input[type=file][id=video-input]", {
            accept: "video/*",
            onchange: (event) => {VideoPlayer.loadVideo(event.target.files[0])},
          }),
          !VideoPlayer.error ? m("label.fa-solid fa-video toolbar-icon", {for: "video-input"}) :
                               m("span.fa-solid fa-ban toolbar-icon input-error"),
          m("span.fa-solid fa-user toolbar-icon", {
            onclick: Layout.loginDialog.state.openDialog,
          }),
        ]),
      ]),
      m("nav.drawer", {id: "drawer"}, [
        m("div", {style: "margin-bottom: 15px;"}, [
          m("h4", "Sessions"),
          m(SessionList)
        ]),
      ]),
      m(Layout.errorDialog, {
        onopen: null,
        onclose: () => {Layout.error = null},
      }, m(ErrorPopup)),
      m(Layout.loginDialog, {
        onopen: null,
        onclose: null,
      }, m(Login, {parentDialog: Layout.loginDialog})),
      Session.current.full_access ? m(Layout.setupDialog, {
        onopen: SetupWizard.onopen,
        onclose: SetupWizard.onclose,
      }, m(SetupWizard, {parentDialog: Layout.setupDialog})) : null,
      vnode.children,
    ])
  }
}

module.exports = Layout
