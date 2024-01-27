var m = require("mithril")

var timestampToString = function(timestamp) {
  return new Date(timestamp * 1e3).toLocaleString(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  })
}

var Session = {
  gpxError: "",
  list: {},
  loadList: function() {
    return m.request({
      method: "GET",
      url: "/api/session",
    })
    .then(function(result) {
      Session.list = {}
      let lastDate = ""
      result.forEach(function(item, index) {
        const d = timestampToString(item.timestamp)
        if (d != lastDate) {
          Session.list[d] = [item]
          lastDate = d
        } else {
          Session.list[d].push(item)
        }
      })
    })
  },
  putNormalized: function(normalizedSession) {
    return m.request({
      method: "PUT",
      url: "/api/session/normalized",
      headers: {
        "X-CSRF-TOKEN": SST.getCookie("csrf_access_token"),
      },
      body: normalizedSession,
    })
    .then(function(result) {
      return result.id
    })
  },
  remove: function(id) {
    return m.request({
      method: "DELETE",
      url: "/api/session/" + id,
      headers: {
        "X-CSRF-TOKEN": SST.getCookie("csrf_access_token"),
      },
    })
    .then(function() {
      let day_idx
      let session_idx
      Object.entries(Session.list).forEach(day => {
        day[1].forEach((session, si) => {
          if (session.id == id) {
            day_idx = day[0]
            session_idx = si
          }
        })
      })
      Session.list[day_idx].splice(session_idx, 1)
      if (Session.list[day_idx].length == 0) {
        delete Session.list[day_idx]
      }
      if (id == Session.current.id) {
        m.route.set("/dashboard")
      }
      m.redraw()
    })
  },
  change: function(name, description) {
    Object.values(Session.list).forEach(day => {
      day.forEach(session => {
        if (session.id == Session.current.id) {
          session.name = name
          session.description = description
        }
      })
    })
    Session.current.name = name
    Session.current.description = description
    m.redraw()
  },
  current: {loaded: false},
  load: function(id) {
    return m.request({
      method: "GET",
      url: "/api/session/" + id + "/bokeh",
    })
    .then(function(result) {
      Session.current = result
      Session.current.loaded = true
      Session.current.divIds = Session.current.divs.filter(e => e !== null).map(div => {
        return div.split("\"")[1]
      })
    })
  },
  patch: function(name, description) {
    return m.request({
      method: "PATCH",
      url: "/api/session/" + Session.current.id,
      headers: {
        "X-CSRF-TOKEN": SST.getCookie("csrf_access_token"),
      },
      body: {"name": name, "desc": description},
    })
    .then(function(result) {
      Session.change(name, description)
    })
  },
  importGPX: async function(event) {
    const file = event.target.files[0];
    const gpx = await file.text();
    return m.request({
      method: "PUT",
      url: "/api/session/" + Session.current.id + "/gpx",
      headers: {
        "Content-Type": "application/octet-stream",
        "X-CSRF-TOKEN": SST.getCookie("csrf_access_token"),
      },
      body: gpx,
      serialize: value => value,
    })
    .then(function(result) {
      if (result !== undefined) {
        SST.update.map(result.full_track, result.session_track);
        Session.current.session_track = result.session_track
      }
    })
    .catch(function(error) {
      if (error.code == 400) {
        Session.gpxError = "GPX not applicable"
        SST.setError(Session.gpxError)
      }
      throw(error)
    })
  },
}

module.exports = Session
