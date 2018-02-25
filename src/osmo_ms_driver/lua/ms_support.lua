json = require("json")
socket = require("socket")
socket.unix = require("socket.unix")

local g_c = socket.unix.dgram()
local g_ms = nil

local mod = {}

-- Register the MS instance with the system
function mod.register(ms, path)
	g_ms = ms

	g_c:connect(path)

	local event = {}
	event['ms'] = g_ms
	event['type'] = 'register'
	g_c:send(json.encode(event))
end

-- Send an event
function mod.send(data)
	local event = {}
	event['ms'] = g_ms
	event['type'] = 'event'
	event['data'] = data
	g_c:send(json.encode(event))
end

return mod
