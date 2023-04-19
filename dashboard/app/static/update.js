const update_plots = function(start, end) {
  const args = "?start=" + start + "&end=" + end;
  fetch('/api/session/' + session_id + '/filter' + args)
    .then((response) => { return response.json(); })
    .then((update) => { process_update_json(update); })
}

const update_fft = function(p, u) {
  p.select_one("ds_fft").data = u.data;
  p.select_one("b_fft").glyph.width = u.width;
}

const update_thist = function(p, u) {
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
}

const update_vhist = function(p, u) {
  p.select_one("ds_hist").data = u.data;
  p.x_range.end = u.mx;
  
  p.select_one("ds_normal").data = u.normal_data;

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
}

const update_vbands = function(p, u) {
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
}

const update_balance = function(p, u) {
  p.select_one("ds_f").data = u.f_data;
  p.select_one("ds_r").data = u.r_data;
  p.x_range.end = u.range_end;
}

const update_map = function(map, full_track, session_track) {
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
  start_point.x = full_track["lon"][0];
  start_point.y = full_track["lat"][0];

  const end_point = map.select_one("end_point");
  end_point.x = full_track["lon"].slice(-1)[0];
  end_point.y = full_track["lat"].slice(-1)[0];
}
