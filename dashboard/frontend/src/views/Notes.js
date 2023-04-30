var m = require("mithril")
var Session = require("../models/Session")
var VideoPlayer = require("./VideoPlayer")

var Notes = {
  dirty: false,
  name: null,
  desc: null,
  oninit: function() {
    Notes.name = Session.current.name
    Notes.desc = Session.current.description
    Notes.dirty = false
  },
  save: function() {
    Session.patch(Notes.name, Notes.desc)
    .then((result) => {
      Notes.name = Session.current.name
      Notes.desc = Session.current.description
      Notes.dirty = false
    })
    .catch((e) => {
      if (e.code == 401) {
        Login.logout()
      }
    })
  },
  view: function(vnode) {
    return m(".description-box", [
      m(".description-title", [
        m(".description-label", "Notes"),
        m("input[type=file][id=video-input]", {
          accept: "video/*",
          onchange: (event) => {VideoPlayer.loadVideo(event.target.files[0])},
        }),
        m("label.video-button", {for: "video-input"}, "load video"),
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
          Notes.dirty = Notes.name != Session.current.name ||
                        Notes.desc != Session.current.description
        },
      }),
      m("textarea.notes-desc", {
        value: Notes.desc,
        disabled: !Session.current.full_access,
        oninput: (event) => {
          Notes.desc = event.target.value
          Notes.dirty = Notes.name != Session.current.name ||
                        Notes.desc != Session.current.description
        },
      })
    ])
  },
}

module.exports = Notes
