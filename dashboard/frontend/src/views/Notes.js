var m = require("mithril")
var Session = require("../models/Session")
var Login = require("./Login.js")
var InputField = require("./InputField")

var SuspensionSetup = {
  view: function() {
    return m("table", [
      m("thead", [
        m("tr", [
          m("td", ""),
          m("td.notes-rowheader", "Front"),
          m("td.notes-rowheader", "Rear"),
        ])
      ]),
      m("tbody", [
        m("tr", [
          m("td.notes-columnheader", "Spring:"),
          m("td.notes-setting", [
            m("input", {
              type: "text",
              value: Notes.suspension_settings.front_springrate,
              disabled: !Session.current.full_access,
              oninput: (event) => {
                Notes.suspension_settings.front_springrate = event.target.value
                Notes.dirty = Notes.is_dirty()
              },
            }),
          ]),
          m("td.notes-setting", [
            m("input", {
              type: "text",
              value: Notes.suspension_settings.rear_springrate,
              disabled: !Session.current.full_access,
              oninput: (event) => {
                Notes.suspension_settings.rear_springrate = event.target.value
                Notes.dirty = Notes.is_dirty()
              },
            }),
          ]),
        ]),
        m("tr", [
          m("td.notes-columnheader", "HSC:"),
          m("td.notes-setting", [
            m("input", {
              type: "number",
              value: Notes.suspension_settings.front_hsc,
              disabled: !Session.current.full_access,
              oninput: (event) => {
                Notes.suspension_settings.front_hsc = event.target.value
                Notes.dirty = Notes.is_dirty()
              },
            }),
          ]),
          m("td.notes-setting", [
            m("input", {
              type: "number",
              value: Notes.suspension_settings.rear_hsc,
              disabled: !Session.current.full_access,
              oninput: (event) => {
                Notes.suspension_settings.rear_hsc = event.target.value
                Notes.dirty = Notes.is_dirty()
              },
            }),
          ]),
        ]),
        m("tr", [
          m("td.notes-columnheader", "LSC:"),
          m("td.notes-setting", [
            m("input", {
              type: "number",
              value: Notes.suspension_settings.front_lsc,
              disabled: !Session.current.full_access,
              oninput: (event) => {
                Notes.suspension_settings.front_lsc = event.target.value
                Notes.dirty = Notes.is_dirty()
              },
            }),
          ]),
          m("td.notes-setting", [
            m("input", {
              type: "number",
              value: Notes.suspension_settings.rear_lsc,
              disabled: !Session.current.full_access,
              oninput: (event) => {
                Notes.suspension_settings.rear_lsc = event.target.value
                Notes.dirty = Notes.is_dirty()
              },
            }),
          ]),
        ]),
        m("tr", [
          m("td.notes-columnheader", "LSR:"),
          m("td.notes-setting", [
            m("input", {
              type: "number",
              value: Notes.suspension_settings.front_lsr,
              disabled: !Session.current.full_access,
              oninput: (event) => {
                Notes.suspension_settings.front_lsr = event.target.value
                Notes.dirty = Notes.is_dirty()
              },
            }),
          ]),
          m("td.notes-setting", [
            m("input", {
              type: "number",
              value: Notes.suspension_settings.rear_lsr,
              disabled: !Session.current.full_access,
              oninput: (event) => {
                Notes.suspension_settings.rear_lsr = event.target.value
                Notes.dirty = Notes.is_dirty()
              },
            }),
          ]),
        ]),
        m("tr", [
          m("td.notes-columnheader", "HSR:"),
          m("td.notes-setting", [
            m("input", {
              type: "number",
              value: Notes.suspension_settings.front_hsr,
              disabled: !Session.current.full_access,
              oninput: (event) => {
                Notes.suspension_settings.front_hsr = event.target.value
                Notes.dirty = Notes.is_dirty()
              },
            }),
          ]),
          m("td.notes-setting", [
            m("input", {
              type: "number",
              value: Notes.suspension_settings.rear_hsr,
              disabled: !Session.current.full_access,
              oninput: (event) => {
                Notes.suspension_settings.rear_hsr = event.target.value
                Notes.dirty = Notes.is_dirty()
              },
            }),
          ]),
        ]),
      ])
    ])
  }
}

var Notes = {
  dirty: false,
  name: null,
  desc: null,
  suspension_settings: null,

  oninit: function() {
    Notes.name = Session.current.name
    Notes.desc = Session.current.description
    Notes.suspension_settings = {
      front_springrate: Session.current.front_springrate,
      rear_springrate: Session.current.rear_springrate,
      front_hsc: Session.current.front_hsc,
      rear_hsc: Session.current.rear_hsc,
      front_lsc: Session.current.front_lsc,
      rear_lsc: Session.current.rear_lsc,
      front_lsr: Session.current.front_lsr,
      rear_lsr: Session.current.rear_lsr,
      front_hsr: Session.current.front_hsr,
      rear_hsr: Session.current.rear_hsr,
    }

    Notes.dirty = false
  },
  save: function() {
    Session.patch(Notes.name, Notes.desc, Notes.suspension_settings)
    .then((result) => {
      Notes.oninit()
    })
    .catch((e) => {
      if (e.code == 401) {
        Login.forceLogout()
      }
    })
  },
  is_dirty: function() {
    return (
      Notes.name != Session.current.name ||
      Notes.desc != Session.current.description ||
      Notes.suspension_settings.front_springrate != Session.current.front_springrate ||
      Notes.suspension_settings.rear_springrate != Session.current.rear_springrate ||
      Notes.suspension_settings.front_hsc != Session.current.front_hsc ||
      Notes.suspension_settings.rear_hsc != Session.current.rear_hsc ||
      Notes.suspension_settings.front_lsc != Session.current.front_lsc ||
      Notes.suspension_settings.rear_lsc != Session.current.rear_lsc ||
      Notes.suspension_settings.front_lsr != Session.current.front_lsr ||
      Notes.suspension_settings.rear_lsr != Session.current.rear_lsr ||
      Notes.suspension_settings.front_hsr != Session.current.front_hsr ||
      Notes.suspension_settings.rear_hsr != Session.current.rear_hsr)
  },
  view: function(vnode) {
    return m(".description-box", [
      m(".description-title", [
        m(".description-label", "Notes"),
        m("button.save-button", {
          disabled: !Session.current.full_access || !Notes.dirty,
          onclick: Notes.save,
        }, "save")
      ]),
      m("input.notes-name", {
        type: "text",
        value: Notes.name,
        disabled: !Session.current.full_access,
        oninput: (event) => {
          Notes.name = event.target.value
          Notes.dirty = Notes.is_dirty()
        },
      }),
      m(SuspensionSetup),
      m("textarea.notes-desc", {
        value: Notes.desc,
        disabled: !Session.current.full_access,
        oninput: (event) => {
          Notes.desc = event.target.value
          Notes.dirty = Notes.is_dirty()
        },
      })
    ])
  },
}

module.exports = Notes
