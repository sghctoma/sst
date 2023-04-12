package db

var Schema = `
	CREATE TABLE IF NOT EXISTS tokens (
		token TEXT NOT NULL
	);
	CREATE TABLE IF NOT EXISTS boards (
		id TEXT PRIMARY KEY,
		setup_id INTEGER NOT NULL,
		FOREIGN KEY (setup_id) REFERENCES setups (id)
	);
	CREATE TABLE IF NOT EXISTS setups(
		id INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
		linkage_id INTEGER NOT NULL,
		front_calibration_id INTEGER,
		rear_calibration_id INTEGER,
		FOREIGN KEY (linkage_id) REFERENCES linkages (id),
		FOREIGN KEY (front_calibration_id) REFERENCES calibrations (id),
		FOREIGN KEY (rear_calibration_id) REFERENCES calibrations (id)
	);
    CREATE TABLE IF NOT EXISTS calibration_methods (
        id INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
		description TEXT,
		data TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS calibrations (
        id INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
		method_id INT NOT NULL,
		inputs TEXT NOT NULL,
		FOREIGN KEY (method_id) REFERENCES calibration_methods (id)
    );
    CREATE TABLE IF NOT EXISTS linkages(
        id INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
		head_angle REAL NOT NULL,
		raw_lr_data TEXT NOT NULL,
		front_stroke REAL NOT NULL,
		rear_stroke REAL NOT NULL
	);
	CREATE TABLE IF NOT EXISTS tracks(
		id INTEGER PRIMARY KEY,
		track TEXT NOT NULL
	);
    CREATE TABLE IF NOT EXISTS sessions(
		id INTEGER PRIMARY KEY,
		name TEXT,
		setup_id INTEGER NOT NULL,
		description TEXT,
		timestamp INTEGER NOT NULL,
		data BLOB NOT NULL,
		track_id INTEGER,
		FOREIGN KEY (setup_id) REFERENCES setups (id),
		FOREIGN KEY (track_id) REFERENCES tracks (id)
	);
	CREATE TABLE IF NOT EXISTS bokeh_components(
		session_id INTEGER PRIMARY KEY,
		script TEXT NOT NULL,
		travel TEXT NOT NULL,
		velocity TEXT NOT NULL,
		map TEXT NOT NULL,
		lr TEXT NOT NULL,
		sw TEXT NOT NULL,
		setup TEXT NOT NULL,
		desc TEXT NOT NULL,
		f_thist TEXT NOT NULL,
		f_fft TEXT NOT NULL,
		f_vhist TEXT NOT NULL,
		r_thist TEXT NOT NULL,
		r_fft TEXT NOT NULL,
		r_vhist TEXT NOT NULL,
		cbalance TEXT NOT NULL,
		rbalance TEXT NOT NULL,
		FOREIGN KEY (session_id) REFERENCES sessions (id)
	);`

var Tokens = `
	SELECT token
	FROM tokens`

var InsertToken = `
	INSERT
	INTO tokens (token)
	VALUES (token)
	RETURNING rowid`

var SetupForBoard = `
	SELECT S.id, S.linkage_id, S.front_calibration_id, S.rear_calibration_id
	FROM setups S
	JOIN boards B
	ON S.id = B.setup_id
	WHERE
	    B.id = ?
		AND S.id = B.setup_id;`

var InsertBoard = `
	INSERT
	INTO boards (id, setup_id)
	VALUES (?, ?)
	RETURNING rowid`

var DeleteBoard = `
	DELETE
	FROM boards
	WHERE id = ?`

var Setups = `
	SELECT *
	FROM setups`

var Setup = `
	SELECT *
	FROM setups
	WHERE id = ?`

var InsertSetup = `
	INSERT
	INTO setups (name, linkage_id, front_calibration_id, rear_calibration_id)
	VALUES (?, ?, ?, ?)
	RETURNING id
	`
var DeleteSetup = `
	DELETE
	FROM setups
	WHERE id = ?`

var CalibrationMethods = `
	SELECT *
	FROM calibration_methods`

var CalibrationMethod = `
	SELECT *
	FROM calibration_methods
	WHERE id = ?`

var InsertCalibrationMethod = `
	INSERT
	INTO calibration_methods (name, description, data)
	VALUES (?, ?, ?)
	RETURNING id
	`
var DeleteCalibrationMethod = `
	DELETE
	FROM calibration_methods
	WHERE id = ?`

var Calibrations = `
	SELECT *
	FROM calibrations`

var Calibration = `
	SELECT *
	FROM calibrations
	WHERE id = ?`

var InsertCalibration = `
	INSERT
	INTO calibrations (name, method_id, inputs)
	VALUES (?, ?, ?)
	RETURNING id
	`
var DeleteCalibration = `
	DELETE
	FROM calibrations
	WHERE id = ?`

var Linkages = `
	SELECT *
	FROM linkages`

var Linkage = `
	SELECT *
	FROM linkages
	WHERE id = ?`

var InsertLinkage = `
	INSERT
	INTO linkages (name, head_angle, raw_lr_data, front_stroke, rear_stroke)
	VALUES (?, ?, ?, ?, ?)
	RETURNING id`

var DeleteLinkage = `
	DELETE
	FROM linkages
	WHERE id = ?`

var Sessions = `
	SELECT id, name, timestamp, description, setup_id
	FROM sessions
	`
var Session = `
	SELECT id, name, timestamp, description, setup_id
	FROM sessions
	WHERE id = ?`

var SessionData = `
	SELECT name, data
	FROM sessions
	WHERE id = ?`

var InsertSession = `
	INSERT
	INTO sessions (name, timestamp, description, setup_id, data)
	VALUES (?, ?, ?, ?, ?)
	RETURNING id`

var DeleteSession = `
	DELETE
	FROM sessions
	WHERE id = ?`

var UpdateSession = `
	UPDATE sessions
	SET (name, description) = (?, ?)
	WHERE id = ?`

var InsertTrack = `
	INSERT
	INTO tracks (track)
	VALUES (?)
	RETURNING id`

var SetTrackForSession = `
	UPDATE sessions
	SET track_id = ?
	WHERE id = ?`
