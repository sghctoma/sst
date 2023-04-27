package db

var SetupForBoard = `
	SELECT S.id, S.linkage_id, S.front_calibration_id, S.rear_calibration_id
	FROM setup S
	JOIN board B
	ON S.id = B.setup_id
	WHERE
	    B.id = ?
		AND S.id = B.setup_id;`

var InsertBoard = `
	INSERT OR IGNORE
	INTO board (id, setup_id)
	VALUES (?, ?)`

var Setup = `
	SELECT linkage_id, front_calibration_id, rear_calibration_id
	FROM setup
	WHERE id = ?;`

var CalibrationMethod = `
	SELECT *
	FROM calibration_method
	WHERE id = ?`

var Calibration = `
	SELECT *
	FROM calibration
	WHERE id = ?`

var Linkage = `
	SELECT *
	FROM linkage
	WHERE id = ?`

var InsertSession = `
	INSERT
	INTO session (name, timestamp, description, setup_id, data)
	VALUES (?, ?, ?, ?, ?)
	RETURNING id`
