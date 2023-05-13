var m = require("mithril")
var Session = require("../models/Session")
var User = require("../models/User")
var Login = require("./Login")


var SessionDayItem = {
 view: function(vnode) {
    return m("div", {style: "display: block; margin: 5px;"}, [
      m("p", {style: "font-size: 14px; color: #d0d0d0; margin-top: 10px;"}, vnode.children[0]),
      m("hr", {style: "margin-top: 3px;"}),
    ])
  } 
}

var SessionListItem = {
  view: function(vnode) {
    return m("div", {style: "display: block;"}, [
      m(".tooltip", {style: "display: inline-block; margin: 5px; margin-left: 15px;"}, [
        m(m.route.Link, {
              style: "display: inline-block;",
              class: "route-link",
              onclick: () => {document.getElementById('drawer-toggle').checked = false;},
              href: "/dashboard/" + vnode.children[0].id
            }, vnode.children[0].name),
        m("span.tooltiptext", vnode.children[0].description != "" ? vnode.children[0].description : "No description")
      ]),
      User.current ? m("button.delete-button", {
        onclick: () => {
          Session.remove(vnode.children[0].id)
          .catch((e) => {
            if (e.code == 401) {
              Login.forceLogout()
            }
          })
        },
      }, "del") : null,
    ])
  }
}

module.exports = {
  oninit: Session.loadList,
  view: function() {
    return m(".session-list", Object.entries(Session.list).map(function([d, s], i) {
      return m(".session-list-day", [m(SessionDayItem, d)].concat(s.map(function(session) {
        return m(SessionListItem, [session])
      })))
    }))
  },
}
