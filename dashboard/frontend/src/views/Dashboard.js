var m = require("mithril")
var Session = require("../models/Session")
var Login = require("./Login")
var Notes = require("./Notes")
var VideoPlayer = require("./VideoPlayer")

var SingleSuspensionTabs = {
  view: function() {
    return m("div", {class: Session.current.session_track || VideoPlayer.loaded ? "tabs" : "tabs novidmap"}, [
      m("input.radiotab", {name: "tabs", tabindex: "1", type: "radio", id: "tabone", checked: "checked"}),
      m("label.label", {style: "grid-column: 1", for: "tabone"}, "Spring rate"),
      m(".panel springrate", {tabindex: "1"}, [
        m(".travel-hist", m.trust(Session.current.divs[5])),
        m(".fft", m.trust(Session.current.divs[6])),
      ]),
      m("input.radiotab", {name: "tabs", tabindex: "1", type: "radio", id: "tabtwo"}),
      m("label.label", {style: "grid-column: 2", for: "tabtwo"}, "Damping"),
      m(".panel damping", {tabindex: "1"}, [
        m(".velocity-hist", m.trust(Session.current.divs[7])),
      ]),
    ])
  }
}

var DualSuspensionTabs = {
  oncreate: function(vnode) {
    const tabOne = vnode.dom.querySelector('#tabone');
    tabOne.checked = true;
  },
  view: function() {
    return m("div", {class: Session.current.session_track || VideoPlayer.loaded ? "tabs" : "tabs novidmap"}, [
      m("input.radiotab", {name: "tabs", tabindex: "1", type: "radio", id: "tabone"}),
      m("label.label", {style: "grid-column: 1", for: "tabone"}, "Spring rate"),
      m(".panel springrate", {tabindex: "1"}, [
        m(".front-travel-hist", m.trust(Session.current.divs[5])),
        m(".rear-travel-hist", m.trust(Session.current.divs[8])),
        m(".front-fft", m.trust(Session.current.divs[6])),
        m(".rear-fft", m.trust(Session.current.divs[9])),
      ]),
      m("input.radiotab", {name: "tabs", tabindex: "1", type: "radio", id: "tabtwo"}),
      m("label.label", {style: "grid-column: 2", for: "tabtwo"}, "Damping"),
      m(".panel damping", {tabindex: "1"}, [
        m(".front-velocity-hist", m.trust(Session.current.divs[7])),
        m(".rear-velocity-hist", m.trust(Session.current.divs[10])),
      ]),
      m("input.radiotab", {name: "tabs", tabindex: "1", type: "radio", id: "tabthree"}),
      m("label.label", {style: "grid-column: 3", for: "tabthree"}, "Balance"),
      m(".panel balance", {tabindex: "1"}, [
        m(".balance-compression", m.trust(Session.current.divs[11])),
        m(".balance-rebound", m.trust(Session.current.divs[12])),
      ]),
    ])
  }
}

function waitForDivs(divIds, callback) {
  const observedDivs = new Set();
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.nodeType === Node.ELEMENT_NODE && divIds.includes(node.id)) {
          observedDivs.add(node.id);
          if (observedDivs.size === divIds.length) {
            callback();
            observer.disconnect();
          }
        }
      }
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

module.exports = {
  oncreate: function(vnode) {
    // Load new session and update dashboard
    Session.load(vnode.attrs.key)
    .then(() => {
      document.getElementById("layout-stylesheet").setAttribute("href",
        Session.current.suspension_count == 1 ? "static/layout-single.css" : "static/layout-double.css")
      document.title = `Sufni Suspenion Telemetry (${Session.current.name})`
      m.redraw()
      waitForDivs(Session.current.divIds, () => {eval(Session.current.script)})
    })
    .catch((error) => {
      if (error.code == 401) {
        Login.forceLogout()
      }
    })
  },
  onremove: function() {
    if (Bokeh.documents.length != 0) {
      Bokeh.documents[0].clear()
      delete Bokeh.documents[0]
      Bokeh.documents.splice(0)
    }
    Session.current = {loaded: false}
    document.getElementById("layout-stylesheet").setAttribute("href", "")
    document.title = "Sufni Suspenion Telemetry"
    m.redraw()
  },
  view: function() {
    return Session.current.loaded ? m(".container", {id: "page-content"}, [
      m(".video-map", [
        m(".map", {style: VideoPlayer.loaded ? "" : "height: 100%"}, m.trust(Session.current.divs[2])),
        m(VideoPlayer),
      ]),
      m("div", {
        class: Session.current.session_track || VideoPlayer.loaded ? "travel" : "travel novidmap"
      }, m.trust(Session.current.divs[0])),
      m("div", {
        class: Session.current.session_track || VideoPlayer.loaded ? "velocity" : "velocity novidmap"
      }, m.trust(Session.current.divs[1])),
      m(".lr", m.trust(Session.current.divs[3])),
      m(".sw", m.trust(Session.current.divs[4])),
      m(".description", m(Notes)),
      Session.current.suspension_count == 2 ? m(DualSuspensionTabs) : m(SingleSuspensionTabs),
    ]) : m("div", "SESSION IS LOADING")
  }
}
