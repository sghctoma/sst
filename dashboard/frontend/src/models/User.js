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
  pwchange: function(old_password, new_password) {
    return m.request({
      method: 'PATCH',
      url: '/auth/pwchange',
      headers: {
        "X-CSRF-TOKEN": SST.getCookie("csrf_access_token"),
      },
      body: {old_password, new_password},
    })
  },
}

module.exports = User
