var m = require("mithril")
var Session = require("../models/Session")

var SingleSuspensionTabs = {
  view: function() {
    return m(".tabs", [
      m("input.radiotab", {name: "tabs", tabindex: "1", type: "radio", id: "tabone", checked: "checked"}),
      m("label.label", {style: "grid-column: 1", for: "tabone"}, "Spring rate"),
      m(".panel springrate", {tabindex: "1"}, [
        m(".travel-hist", m.trust(Session.current.divs[7] ? Session.current.divs[7] : Session.current.divs[10])),
        m(".fft", m.trust(Session.current.divs[8] ? Session.current.divs[8] : Session.current.divs[11])),
      ]),
      m("input.radiotab", {name: "tabs", tabindex: "1", type: "radio", id: "tabtwo"}),
      m("label.label", {style: "grid-column: 2", for: "tabtwo"}, "Damping"),
      m(".panel damping", {tabindex: "1"}, [
        m(".velocity-hist", m.trust(Session.current.divs[9] ? Session.current.divs[9] : Session.current.divs[12])),
      ]),
    ])
  }
}

var DualSuspensionTabs = {
  view: function() {
    return m(".tabs", [
      m("input.radiotab", {name: "tabs", tabindex: "1", type: "radio", id: "tabone", checked: "checked"}),
      m("label.label", {style: "grid-column: 1", for: "tabone"}, "Spring rate"),
      m(".panel springrate", {tabindex: "1"}, [
        m(".front-travel-hist", m.trust(Session.current.divs[7])),
        m(".rear-travel-hist", m.trust(Session.current.divs[10])),
        m(".front-fft", m.trust(Session.current.divs[8])),
        m(".rear-fft", m.trust(Session.current.divs[11])),
      ]),
      m("input.radiotab", {name: "tabs", tabindex: "1", type: "radio", id: "tabtwo"}),
      m("label.label", {style: "grid-column: 2", for: "tabtwo"}, "Damping"),
      m(".panel damping", {tabindex: "1"}, [
        m(".front-velocity-hist", m.trust(Session.current.divs[9])),
        m(".rear-velocity-hist", m.trust(Session.current.divs[12])),
      ]),
      m("input.radiotab", {name: "tabs", tabindex: "1", type: "radio", id: "tabthree"}),
      m("label.label", {style: "grid-column: 3", for: "tabthree"}, "Balance"),
      m(".panel balance", {tabindex: "1"}, [
        m(".balance-compression", m.trust(Session.current.divs[13])),
        m(".balance-rebound", m.trust(Session.current.divs[14])),
      ]),
    ])
  }
}

var NoMap = {
  view: function() {
    return m(".nomap", {id: "nomap", style:"min-height: 400px; z-index: 1; background: #15191c;"}, [
      m("span.static-label", "No GPX track")
    ])
  }
}

var NoMapWithUpload = {
  view: function() {
    return m(".nomap", {id: "nomap", style:"min-height: 400px; z-index: 1; background: #15191c;"}, [
      m("label.drop-container", {for: "track-selector"}, [
        m("span.drop-title", "Upload GPX track"),
        m("input", {
          type: "file",
          id: "track-selector",
          accept: ".gpx",
          onchange:  async function(event) {
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
              } else {
                alert("GPX track is not applicable!");
              };
            })
            .then((data) => {
              if (data !== undefined) {
                document.getElementById("nomap").remove();
                const map = Bokeh.documents[0].get_model_by_name("map");
                map.visible = true;
                SST.update.map(map, data.full_track, data.session_track);
              }
            })
          }
        })
      ])
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
  oncreate: async function(vnode) {
    // Clean up previous Bokeh document
    if (Bokeh.documents.length != 0) {
      Bokeh.documents[0].clear()
      delete Bokeh.documents[0]
      Bokeh.documents.splice(0)
    }

    // Load new session and update dashboard
    await Session.load(vnode.attrs.key)
    document.getElementById("layout-stylesheet").setAttribute("href",
      Session.current.suspension_count == 1 ? "static/layout-single.css" : "static/layout-double.css")
    document.title = `Sufni Suspenion Telemetry (${Session.current.name})`
    m.redraw()
    waitForDivs(Session.current.divIds, () => {eval(Session.current.script)})
  },
  view: function() {
    return Session.current.loaded ? m(".container", {id: "page-content"}, [
      m(".travel", m.trust(Session.current.divs[0])),
      m(".velocity", m.trust(Session.current.divs[1])),
      m(".lr", m.trust(Session.current.divs[3])),
      m(".sw", m.trust(Session.current.divs[4])),
      m(".setup", m.trust(Session.current.divs[5])),
      m(".description", m.trust(Session.current.divs[6])),
      m(".map", {style: "height: 400px;"}, m.trust(Session.current.divs[2])),
      Session.current.session_track == 'undefined' ? null : (Session.current.full_access ? m(NoMapWithUpload) : m(NoMap)),
      Session.current.suspension_count == 2 ? m(DualSuspensionTabs) : m(SingleSuspensionTabs),
    ]) : m("div", "SESSION IS LOADING")
  }
}
