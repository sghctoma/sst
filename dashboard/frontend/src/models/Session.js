var m = require("mithril")

var Session = {
  list: {},
  loadList: function() {
    return m.request({
      method: "GET",
      url: "/api/session",
      withCredentials: true,
    })
    .then(function(result) {
      let lastDate = "";
      result.forEach(function(item, index) {
        const options = {month: "2-digit", day: "2-digit", year: "numeric" }
        const d = new Date(item.timestamp * 1e3).toLocaleString("hu-HU", options)
        if (d != lastDate) {
          Session.list[d] = [item];
          lastDate = d;
        } else {
          Session.list[d].push(item);
        }
      });
    })
  },
  remove: function(id) {
    return m.request({
      method: "DELETE",
      url: "/api/session/" + id,
      headers: {
        "X-CSRF-TOKEN": SST.getCookie("csrf_access_token"),
      },
      withCredentials: true,
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
      url: "/bokeh/" + id,
      withCredentials: true,
    })
    .then(function(result) {
      Session.current = result
      Session.current.loaded = true
    })
  }
}

module.exports = Session