var m = require("mithril")
var Session = require("./Session")
var Login = require("../views/Login")
var VideoPlayer = require("../views/VideoPlayer")
var Layout = require("../views/Layout")

var SST = {
  setError: function(error) {
    Layout.setError(error)
  },
  getCookie: function (name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
  },
  init_models: function() {
    // Store travel graph Span in VideoPlayer
    VideoPlayer.travelSpan = Bokeh.documents[0].get_model_by_name("s_current_time")

    // Map
    SST.update.map(Session.current.full_track, Session.current.session_track)

    // Disable tools on mobile
    if( /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ) {
      const disable_tools = function(item) {
        if (item.toolbar) {
          if (item.toolbar.active_drag) { item.toolbar.active_drag = null; }
          if (item.active_scroll) { item.active_scroll = null; }
          if (item.active_inspect) { item.active_inspect = null; }
        }
      };
      Bokeh.documents[0].roots().forEach(item => {
        disable_tools(item);
        if (item.children) {
          item.children.forEach(child => disable_tools(child));
        }
      });
    }
  },
  seekVideo: VideoPlayer.seek,
  update: {
    process_double_json: function(u) {
      const f_fft = Bokeh.documents[0].get_model_by_name("front_fft");
      const r_fft = Bokeh.documents[0].get_model_by_name("rear_fft");
      const f_thist = Bokeh.documents[0].get_model_by_name("front_travel_hist");
      const r_thist = Bokeh.documents[0].get_model_by_name("rear_travel_hist");
      const f_vhist = Bokeh.documents[0].get_model_by_name("front_velocity_hist");
      const r_vhist = Bokeh.documents[0].get_model_by_name("rear_velocity_hist");
      const cbalance = Bokeh.documents[0].get_model_by_name("balance_compression");
      const rbalance = Bokeh.documents[0].get_model_by_name("balance_rebound");

      SST.update.fft(f_fft, u.front.fft);
      SST.update.fft(r_fft, u.rear.fft);
      SST.update.thist(f_thist, u.front.thist);
      SST.update.thist(r_thist, u.rear.thist);
      SST.update.vhist(f_vhist.children[1], f_vhist.children[0], u.front.vhist);
      SST.update.vhist(r_vhist.children[1], r_vhist.children[0], u.rear.vhist);
      SST.update.vbands(f_vhist.children[2], u.front.vbands);
      SST.update.vbands(r_vhist.children[2], u.rear.vbands);
      SST.update.balance(cbalance, u.balance.compression);
      SST.update.balance(rbalance, u.balance.rebound);
    },
    process_single_json: function(u) {
      const fft = Bokeh.documents[0].get_model_by_name("fft");
      const thist = Bokeh.documents[0].get_model_by_name("travel_hist");
      const vhist = Bokeh.documents[0].get_model_by_name("velocity_hist");

      if (u.front !== null) {
        SST.update.fft(fft, u.front.fft);
        SST.update.thist(thist, u.front.thist);
        SST.update.vhist(vhist.children[1], vhist.children[0], u.front.vhist);
        SST.update.vbands(vhist.children[2], u.front.vbands);
      } else {
        SST.update.fft(fft, u.rear.fft);
        SST.update.thist(thist, u.rear.thist);
        SST.update.vhist(vhist.children[1], vhist.children[0], u.rear.vhist);
        SST.update.vbands(vhist.children[2], u.rear.vbands);
      }
    },
    plots: function(start, end) {
      const args = "?start=" + start + "&end=" + end;
      m.request({
        method: "GET",
        url: '/api/session/' + Session.current.id + '/filter' + args,
      })
      .then((update) => {
          Session.current.suspension_count == 2 ? SST.update.process_double_json(update) :
                                                  SST.update.process_single_json(update);
      })
    },
    fft: function(p, u) {
      p.select_one("ds_fft").data = u.data;
      p.select_one("b_fft").glyph.width = u.width;
    },
    thist: function(p, u) {
      p.select_one("ds_hist").data = u.data;
      p.x_range.end = u.range_end;

      const l_avg = p.select_one("l_avg");
      l_avg.text = u.avg_text;
      l_avg.x = u.range_end;
      l_avg.y = u.avg;
      const l_max = p.select_one("l_max");
      l_max.x = u.range_end;
      l_max.y = u.mx;
      const s_avg = p.select_one("s_avg");
      s_avg.location = u.avg;
      const s_max = p.select_one("s_max");
      s_max.location = u.mx;
    },
    vhist: function(p, p_lowspeed, u) {
      p.select_one("ds_hist").data = u.data;
      p.x_range.end = u.mx;
      p_lowspeed.select_one("ds_hist_lowspeed").data = u.data_lowspeed;
      p_lowspeed.x_range.end = u.mx_lowspeed;
  
      p.select_one("ds_normal").data = u.normal_data;
      p_lowspeed.select_one("ds_normal_lowspeed").data = u.normal_data_lowspeed;

      const top = p.y_range.end;
      const bottom = p.y_range.start;

      p.select_one("s_avgr").location = u.avgr;
      p.select_one("s_avgc").location = u.avgc;
      p.select_one("s_maxr").location = u.maxr;
      p.select_one("s_maxc").location = u.maxc;

      const l_avgr = p.select_one("l_avgr");
      l_avgr.x = u.mx;
      l_avgr.y = u.avgr;
      l_avgr.text = u.avgr_text;
      const l_maxr = p.select_one("l_maxr");
      l_maxr.x = u.mx;
      l_maxr.y = Math.max(top, u.maxr);
      l_maxr.text = u.maxr_text;;
      const l_avgc = p.select_one("l_avgc");
      l_avgc.x = u.mx;
      l_avgc.y = u.avgc;
      l_avgc.text = u.avgc_text;
      const l_maxc = p.select_one("l_maxc");
      l_maxc.x = u.mx;
      l_maxc.y = Math.min(bottom, u.maxc);
      l_maxc.text = u.maxc_text;
    },
    vbands: function(p, u) {
      p.select_one("ds_stats").data = u.data;
  
      const l_hsr = p.select_one("l_hsr");
      l_hsr.text = u.hsr_text;
      l_hsr.y = u.hsc + u.lsc + u.lsr + u.hsr / 2;
      const l_lsr = p.select_one("l_lsr");
      l_lsr.text = u.lsr_text;
      l_lsr.y = u.hsc + u.lsc + u.lsr / 2;
      const l_lsc = p.select_one("l_lsc");
      l_lsc.text = u.lsc_text;
      l_lsc.y = u.hsc + u.lsc / 2;
      const l_hsc = p.select_one("l_hsc");
      l_hsc.text = u.hsc_text;
      l_hsc.y = u.hsc / 2;

      p.y_range.end = u.hsr + u.lsr + u.lsc + u.hsc;
    },
    balance: function(p, u) {
      p.select_one("ds_f").data = u.f_data;
      p.select_one("ds_r").data = u.r_data;
      p.x_range.end = u.range_end;
    },
    map: function(full_track, session_track) {
      const map = Bokeh.documents[0].get_model_by_name("map");
      if (session_track) {
        const start_lon = session_track["lon"][0];
        const start_lat = session_track["lat"][0];

        map.select_one("ds_track").data = full_track;
        map.select_one("ds_session").data = session_track;

        const ratio = map.inner_height / map.inner_width;
        map.x_range.start = start_lon - 600;
        map.x_range.end = start_lon + 600;
        map.y_range.start = start_lat - (600 * ratio);
        map.y_range.end = start_lat + (600 * ratio);

        const start_point = map.select_one("start_point");
        start_point.size = 10
        start_point.x = full_track["lon"][0];
        start_point.y = full_track["lat"][0];

        const end_point = map.select_one("end_point");
        end_point.size = 10
        end_point.x = full_track["lon"].slice(-1)[0];
        end_point.y = full_track["lat"].slice(-1)[0];

        map.select_one("pos_marker").size = 13
      } else {
        // visible = false does not work, so we just set the size to 0
        Bokeh.documents[0].get_model_by_name("start_point").size = 0
        Bokeh.documents[0].get_model_by_name("end_point").size = 0
        Bokeh.documents[0].get_model_by_name("pos_marker").size = 0
      }
    },
  }
}

module.exports = SST
