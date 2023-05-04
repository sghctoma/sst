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

var loadGPX = async function(event) {
  const file = event.target.files[0];
  const gpx = await file.text();
  const params = {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/octet-stream",
      "X-CSRF-TOKEN": SST.getCookie("csrf_access_token"),
    },
    body: gpx
  }
  fetch(
    "/api/gpx/" + Session.current.id, params
  )
  .then((response) => {
    if (response.ok) {
      return response.json();
    } else if (response.status == 401) {
      Login.logout()
    } else {
      alert("GPX track is not applicable!");
    };
  })
  .then((data) => {
    if (data !== undefined) {
      SST.update.map(data.full_track, data.session_track);
      Session.current.session_track = data.session_track
      m.redraw()
    }
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
            onchange: loadGPX,
          }) : null,
          Session.current.full_access ? m("label.fa-solid fa-map-location-dot toolbar-icon", {
            for: "gpx-input",
          }) : null,
          m("input[type=file][id=video-input]", {
            accept: "video/*",
            onchange: (event) => {VideoPlayer.loadVideo(event.target.files[0])},
          }),
          m("label.fa-solid fa-video toolbar-icon", {for: "video-input"}),
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
