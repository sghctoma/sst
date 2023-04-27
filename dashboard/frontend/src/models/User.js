var m = require("mithril")

var User = {
  current: null,
  check: function() {
    return m.request({
      method: 'GET',
      url: '/auth/user'
    })
    .then(function(user) {
      User.current = user.username
    })
    .catch(function(e) {
      User.logout()
      throw(e)
    })
  },
  login: function(username, password) {
    return m.request({
      method: 'POST',
      url: '/auth/login',
      headers: {
        'Content-Type': 'application/json',
      },
      body: {username, password},
    })
    .then(function(result) {
      User.current = username
    })
    .catch(function(e) {
      User.current = null
      throw(e)
    })
  },
  logout: function() {
    return m.request({
      method: 'POST',
      url: '/auth/logout',
    })
    .then(function() {
      User.current = null
    })
  },
}

module.exports = User
