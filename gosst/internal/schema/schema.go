package schema

var Sql = `
	CREATE TABLE IF NOT EXISTS tokens (
		token TEXT NOT NULL
	);
	CREATE TABLE IF NOT EXISTS boards (
		board_id TEXT PRIMARY KEY,
		setup_id INTEGER NOT NULL,
		FOREIGN KEY (setup_id) REFERENCES setups (setup_id)
	);
	CREATE TABLE IF NOT EXISTS setups(
		setup_id INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
		linkage_id INTEGER NOT NULL,
		front_calibration_id INTEGER NOT NULL,
		rear_calibration_id INTEGER NOT NULL,
		FOREIGN KEY (linkage_id) REFERENCES linkages (linkage_id),
		FOREIGN KEY (front_calibration_id) REFERENCES calibrations (calibration_id),
		FOREIGN KEY (rear_calibration_id) REFERENCES calibrations (calibration_id)
	);
    CREATE TABLE IF NOT EXISTS calibrations (
        calibration_id INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
        arm REAL NOT NULL,
        dist REAL NOT NULL,
        stroke REAL NOT NULL,
        angle REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS linkages(
        linkage_id INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
		raw_lr_data TEXT NOT NULL
	);
	CREATE TABLE IF NOT EXISTS tracks(
		track_id INTEGER PRIMARY KEY,
		track TEXT NOT NULL
	);
    CREATE TABLE IF NOT EXISTS sessions(
		session_id INTEGER PRIMARY KEY,
		name TEXT,
		setup_id INTEGER NOT NULL,
		description TEXT,
		timestamp INTEGER,
		data BLOB,
		track_id INTEGER NOT NULL,
		FOREIGN KEY (setup_id) REFERENCES setups (setup_id),
		FOREIGN KEY (track_id) REFERENCES tracks (track_id)
	);
	CREATE TABLE IF NOT EXISTS bokeh_cache(
		session_id INTEGER NOT NULL,
		script TEXT NOT NULL,
		div_travel TEXT NOT NULL,
		div_velocity TEXT NOT NULL,
		div_map TEXT NOT NULL,
		div_lr TEXT NOT NULL,
		div_sw TEXT NOT NULL,
		div_setup TEXT NOT NULL,
		json_f_fft TEXT,
		json_r_fft TEXT,
		json_f_thist TEXT,
		json_r_thist TEXT,
		json_f_vhist TEXT,
		json_r_vhist TEXT,
		json_cbalance TEXT,
		json_rbalance TEXT,
		FOREIGN KEY (session_id) REFERENCES sessions (session_id)
	);`