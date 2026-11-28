-- ActionDirector v1 (tataku family) : no-dialogue action shorts for Roblox Studio
-- Put this LocalScript in StarterPlayer.StarterPlayerScripts. Press F5 to play the scene.
-- Needs: workspace.ActionLab with Actors (R15 models) and an Arena. See SKILL.md.
local RS = game:GetService("ReplicatedStorage")
if RS:GetAttribute("ActionScene") == false then return end
local RunService = game:GetService("RunService")
local Lighting = game:GetService("Lighting")
local Players = game:GetService("Players")
local cam = workspace.CurrentCamera
local lab = workspace:WaitForChild("ActionLab")
local actorsF = lab:WaitForChild("Actors")
local O = lab:GetAttribute("Origin") or Vector3.zero -- all positions below are relative to this

-- ================= EDIT FROM HERE =================
-- animation ids (Roblox defaults work for everyone; add your own generated ones)
local ANIM = { idle = 507766388, run = 507767714, jump = 507765000, fall = 507767968 }
-- time scale segments {from, to, scale}  (0.3 = slow motion)
local SLOW = { { 4.6, 6.4, 0.3 }, { 10.0, 11.0, 0.35 } }
-- cameras: {t, kind, ...}
--  {"at", t, pos(Vector3), look(Vector3 or actor name), fov, push(0..1 move toward look), roll(deg)}
--  {"follow", t, objectName, offset(Vector3), fov}
local SHOTS = {
	{ "at", 0.0, Vector3.new(0, 40, 70), Vector3.new(0, 4, 0), 50, 0.25 },
	{ "at", 2.0, Vector3.new(-6, 3, 20), "Villain", 45, 0.15 },
	{ "at", 3.4, Vector3.new(-7, 1.5, 3), "Villain", 40, 0.1, -10 },
	{ "follow", 4.6, "Rocket", Vector3.new(3, 1.2, 4), 55 },
	{ "at", 5.6, Vector3.new(17, 3, 22), "Hero", 50, 0.2 },
	{ "at", 6.3, Vector3.new(24, 5, 24), Vector3.new(6, 3, 4), 55, 0.1 },
	{ "at", 7.6, Vector3.new(-8, 5, 1), "Villain", 30, 0.25 },
	{ "at", 8.4, Vector3.new(16, 1.5, 14), "Hero", 55, 0.1, 8 },
	{ "follow", 10.0, "Kunai", Vector3.new(-2, 1, 3), 50 },
	{ "at", 11.0, Vector3.new(-8.5, 5, 0.5), "Villain", 28, 0.0 },
	{ "at", 12.2, Vector3.new(-2, 6, 16), Vector3.new(-16, 4, -8), 55, 0.15 },
}
-- events: {t, name, ...}
local EVENTS = {
	{ 0.0, "card", "ROUND 1", "0 : 0" },
	{ 1.6, "uncard" },
	{ 0.0, "pose", "Hero", "idle" }, { 0.0, "pose", "Villain", "idle" },
	{ 2.4, "move", "Hero", Vector3.new(12, 0, 6), Vector3.new(6, 0, 4), 0.9, 0 },
	{ 3.4, "aim", "Villain", true }, { 6.0, "aim", "Villain", false }, { 9.7, "aim", "Hero", true }, { 10.6, "aim", "Hero", false },
	{ 4.6, "fire", "Rocket", "Villain", "Hero", 1.8, Color3.fromRGB(255, 140, 40) },
	{ 5.7, "move", "Hero", Vector3.new(6, 0, 4), Vector3.new(10, 0, 12), 0.6, 5 },
	{ 6.4, "explode", Vector3.new(6, 3, 4) },
	{ 8.5, "move", "Hero", Vector3.new(10, 0, 12), Vector3.new(14, 16, 0), 1.2, 10 },
	{ 10.0, "fire", "Kunai", "Hero", "Villain", 1.0, Color3.fromRGB(200, 220, 255) },
	{ 11.0, "hit", "Villain" },
	{ 11.0, "freeze", 0.9 },
	{ 11.1, "killfeed", "NINJA", "VILLAIN" }, { 13.3, "killfeed" },
	{ 12.0, "knock", "Villain", Vector3.new(-12, 0, -12) },
	{ 13.4, "card", "ROUND 1", "1 : 0", "NINJA WINS" },
}
local END = 15.5
-- ================= EDIT TO HERE ===================

local function actor(n) return actorsF:FindFirstChild(n) end
-- ---------- setup actors ----------
local TR = {}
for _, m in ipairs(actorsF:GetChildren()) do
	local hum = m:FindFirstChildOfClass("Humanoid"); local root = m:FindFirstChild("HumanoidRootPart")
	if hum and root then
		hum.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
		for _, p in ipairs(m:GetDescendants()) do if p:IsA("BasePart") then p.Anchored = false; p.CanCollide = false end end
		root.Anchored = true
		local a = m:FindFirstChild("Animate"); if a then a:Destroy() end
		local an = hum:FindFirstChildOfClass("Animator") or Instance.new("Animator", hum)
		TR[m.Name] = { root = root, cf0 = root.CFrame, tracks = {} }
		for k, id in pairs(ANIM) do
			local A = Instance.new("Animation"); A.AnimationId = "rbxassetid://" .. id
			local ok, tr = pcall(function() return an:LoadAnimation(A) end)
			if ok then tr.Looped = (k == "idle" or k == "run"); TR[m.Name].tracks[k] = tr end
		end
	end
end
local function pose(n, k)
	local a = TR[n]; if not a then return end
	if a.cur == k then return end
	if a.cur and a.tracks[a.cur] then a.tracks[a.cur]:Stop(0.15) end
	a.cur = k; if a.tracks[k] then a.tracks[k]:Play(0.15) end
end
-- ---------- gui ----------
local pg = Players.LocalPlayer:WaitForChild("PlayerGui")
local gui = Instance.new("ScreenGui"); gui.IgnoreGuiInset = true; gui.ResetOnSpawn = false; gui.Parent = pg
local card = Instance.new("Frame", gui); card.Size = UDim2.fromScale(1, 1); card.BackgroundColor3 = Color3.fromRGB(20, 60, 200); card.Visible = false
local function lbl(parent, y, h, col)
	local l = Instance.new("TextLabel", parent); l.Size = UDim2.fromScale(1, h); l.Position = UDim2.fromScale(0, y); l.BackgroundTransparency = 1
	l.Font = Enum.Font.GothamBlack; l.TextScaled = true; l.TextColor3 = col; l.TextStrokeTransparency = 0; return l
end
local c1, c2, c3 = lbl(card, 0.18, 0.12, Color3.new(1, 1, 1)), lbl(card, 0.36, 0.28, Color3.fromRGB(255, 50, 50)), lbl(card, 0.7, 0.1, Color3.fromRGB(255, 230, 0))
local flash = Instance.new("Frame", gui); flash.Size = UDim2.fromScale(1, 1); flash.BackgroundColor3 = Color3.new(1, 1, 1); flash.BackgroundTransparency = 1
local hm = Instance.new("TextLabel", gui); hm.Size = UDim2.fromOffset(160, 160); hm.AnchorPoint = Vector2.new(0.5, 0.5); hm.Position = UDim2.fromScale(0.5, 0.5)
hm.BackgroundTransparency = 1; hm.Text = ""; hm.Visible = false
for _, r in ipairs({ 45, -45 }) do local bar = Instance.new("Frame", hm); bar.AnchorPoint = Vector2.new(0.5, 0.5); bar.Position = UDim2.fromScale(0.5, 0.5); bar.Size = UDim2.fromScale(1, 0.16); bar.Rotation = r; bar.BackgroundColor3 = Color3.fromRGB(255, 40, 40); bar.BorderSizePixel = 0 end
for _, e in ipairs(Lighting:GetChildren()) do if e:IsA("DepthOfFieldEffect") then e.Enabled = false end end
local kf = Instance.new("Frame", gui); kf.AnchorPoint = Vector2.new(0.5, 0); kf.Position = UDim2.fromScale(0.5, 0.06); kf.Size = UDim2.fromScale(0.5, 0.06); kf.BackgroundColor3 = Color3.fromRGB(15, 15, 20); kf.BackgroundTransparency = 0.2; kf.Visible = false
Instance.new("UICorner", kf).CornerRadius = UDim.new(0.5, 0)
local kft = Instance.new("TextLabel", kf); kft.Size = UDim2.fromScale(1, 1); kft.BackgroundTransparency = 1; kft.Font = Enum.Font.GothamBlack; kft.TextScaled = true; kft.RichText = true; kft.TextColor3 = Color3.new(1, 1, 1)
local cc = Lighting:FindFirstChild("ActionCC") or Instance.new("ColorCorrectionEffect", Lighting); cc.Name = "ActionCC"
-- ---------- state ----------
local objs, moves, shake, freezeUntil, fx = {}, {}, { 0, 0, 0 }, -1, {}
local function screenPos(p) local v, on = cam:WorldToViewportPoint(p) return on and UDim2.fromOffset(v.X, v.Y) or UDim2.fromScale(0.5, 0.5) end
local function spawnProj(name, col)
	local big = not name:lower():find("kunai") and not name:lower():find("arrow")
	local L, W = big and 2.6 or 1.4, big and 0.7 or 0.22
	local p = Instance.new("Part"); p.Name = name; p.Anchored = true; p.CanCollide = false; p.Size = Vector3.new(W, W, L)
	p.Color = big and Color3.fromRGB(90, 95, 105) or Color3.fromRGB(70, 70, 80); p.Material = Enum.Material.Metal
	local nose = Instance.new("Part"); nose.Name = "Nose"; nose.Anchored = true; nose.CanCollide = false; nose.Size = Vector3.new(W, W * 1.6, W); nose.Color = col; nose.Material = Enum.Material.Neon
	local mesh = Instance.new("SpecialMesh", nose); mesh.MeshType = Enum.MeshType.FileMesh; mesh.MeshId = "rbxassetid://1033714"; mesh.Scale = Vector3.new(W * 0.55, W * 1.1, W * 0.55); nose.Parent = p
	local a0 = Instance.new("Attachment", p); a0.Position = Vector3.new(0, W * 0.5, L / 2); local a1 = Instance.new("Attachment", p); a1.Position = Vector3.new(0, -W * 0.5, L / 2)
	local tr = Instance.new("Trail", p); tr.Attachment0 = a0; tr.Attachment1 = a1; tr.Lifetime = big and 0.8 or 0.4; tr.Color = ColorSequence.new(Color3.new(1, 1, 1)); tr.Transparency = NumberSequence.new(0.1, 1); tr.FaceCamera = true
	if big then local fl = Instance.new("Attachment", p); fl.Position = Vector3.new(0, 0, L / 2 + 0.2)
		local pe = Instance.new("ParticleEmitter", fl); pe.Rate = 120; pe.Lifetime = NumberRange.new(0.2, 0.4); pe.Speed = NumberRange.new(2, 5); pe.EmissionDirection = Enum.NormalId.Back
		pe.Color = ColorSequence.new(Color3.fromRGB(255, 200, 60), Color3.fromRGB(255, 80, 20)); pe.Size = NumberSequence.new(0.8, 0); pe.LightEmission = 1 end
	p.Parent = lab; objs[name] = p; return p
end
local function explode(pos)
	flash.BackgroundTransparency = 0; shake = { 1.2, os.clock(), 0.6 }
	local b = Instance.new("Part"); b.Shape = Enum.PartType.Ball; b.Anchored = true; b.CanCollide = false; b.Material = Enum.Material.Neon; b.Color = Color3.fromRGB(255, 150, 30); b.Position = pos; b.Size = Vector3.one; b.Parent = lab
	table.insert(fx, { b, 0 })
	for i = 1, 18 do
		local d = Instance.new("Part"); d.Size = Vector3.one * math.random(6, 14) / 10; d.Color = Color3.fromRGB(90, 90, 90); d.Position = pos + Vector3.new(math.random(-2, 2), 1, math.random(-2, 2))
		d.Parent = lab; d.AssemblyLinearVelocity = Vector3.new(math.random(-30, 30), math.random(20, 50), math.random(-30, 30)); game:GetService("Debris"):AddItem(d, 4)
	end
end
-- ---------- event runner ----------
local done = {}
local function runEvent(e, st)
	local n = e[2]
	if n == "card" then card.Visible = true; c1.Text = e[3] or ""; c2.Text = e[4] or ""; c3.Text = e[5] or ""
	elseif n == "uncard" then card.Visible = false
	elseif n == "killfeed" then kf.Visible = e[3] ~= nil; if e[3] then kft.Text = ("  %s  <font color='#FF3B3B'>KO</font>  %s  "):format(e[3], e[4] or "") end
	elseif n == "pose" then pose(e[3], e[4])
	elseif n == "aim" then local A = actor(e[3]); local sh = A and A:FindFirstChild("RightShoulder", true) -- raise right arm forward (Motor6D or AnimationConstraint rigs)
		local obj, prop = sh, "C0"; if sh and sh:IsA("AnimationConstraint") then obj, prop = sh.Attachment0, "CFrame" end
		if obj then obj:SetAttribute("Orig", obj:GetAttribute("Orig") or obj[prop]); obj[prop] = e[4] and (obj:GetAttribute("Orig") * CFrame.Angles(math.rad(90), 0, 0)) or obj:GetAttribute("Orig") end
	elseif n == "move" then local a = TR[e[3]]; if a then table.insert(moves, { a = a, n = e[3], from = e[4] + O, to = e[5] + O, t0 = st, d = e[6], h = e[7] or 0 }) end
	elseif n == "fire" then local p = spawnProj(e[3], e[7] or Color3.new(1, 1, 1)); local A, B = actor(e[4]), actor(e[5])
		table.insert(moves, { proj = p, from = A.HumanoidRootPart.Position + Vector3.new(0, 1, 0), to = B.HumanoidRootPart.Position + Vector3.new(0, 1, 0), t0 = st, d = e[6] })
	elseif n == "explode" then explode(e[3] + O)
	elseif n == "hit" then local A = actor(e[3]); hm.Visible = true; hm.Position = screenPos(A.Head.Position); flash.BackgroundTransparency = 0.4; shake = { 0.6, os.clock(), 0.35 }
		for k, o in pairs(objs) do o:Destroy(); objs[k] = nil end
	elseif n == "freeze" then freezeUntil = os.clock() + (e[3] or 0.8); cc.Saturation = -1; cc.Contrast = 0.25
		for _, a in pairs(TR) do for _, tr in pairs(a.tracks) do tr:AdjustSpeed(0) end end
	elseif n == "knock" then local a = TR[e[3]]; hm.Visible = false
		table.insert(moves, { a = a, n = e[3], from = a.root.Position - Vector3.new(0, a.cf0.Position.Y - O.Y, 0), to = a.root.Position - Vector3.new(0, a.cf0.Position.Y - O.Y, 0) + e[4], t0 = st, d = 0.9, h = 6, lie = true })
	end
end
-- ---------- clock ----------
local function scaleAt(st) for _, s in ipairs(SLOW) do if st >= s[1] and st < s[2] then return s[3] end end return 1 end
local st, last, started = 0, nil, false
local function shotAt(t) local s for _, x in ipairs(SHOTS) do if t >= x[2] then s = x end end return s end
local function lookPos(v) if typeof(v) == "Vector3" then return v + O end local a = actor(v); return a and a.Head.Position or Vector3.zero end
RunService:BindToRenderStep("ActionDirector", Enum.RenderPriority.Camera.Value + 1, function()
	if not started then return end
	local now = os.clock(); local dt = last and (now - last) or 0; last = now
	if now < freezeUntil then dt = 0 elseif cc.Saturation < 0 then cc.Saturation = 0; cc.Contrast = 0; for _, a in pairs(TR) do for _, tr in pairs(a.tracks) do tr:AdjustSpeed(scaleAt(st)) end end end
	local STL = RS:GetAttribute("LabStill"); if STL and st >= STL then dt = 0 end -- pause at this time for checking
	local ts = scaleAt(st); st += dt * ts
	for _, a in pairs(TR) do for _, tr in pairs(a.tracks) do if tr.IsPlaying and now >= freezeUntil then tr:AdjustSpeed(ts) end end end
	for i, e in ipairs(EVENTS) do if not done[i] and st >= e[1] then done[i] = true; runEvent(e, st) end end
	-- moves
	for i = #moves, 1, -1 do
		local m = moves[i]; local k = math.clamp((st - m.t0) / m.d, 0, 1)
		local p = m.from:Lerp(m.to, k) + Vector3.new(0, 4 * (m.h or 0) * k * (1 - k), 0)
		if m.proj then m.proj.CFrame = CFrame.lookAt(p, m.to); local nz = m.proj:FindFirstChild("Nose"); if nz then nz.CFrame = m.proj.CFrame * CFrame.new(0, 0, -m.proj.Size.Z / 2 - nz.Size.Y * 0.45) * CFrame.Angles(math.rad(-90), 0, 0) end
		else
			local dir = (m.to - m.from) * Vector3.new(1, 0, 1)
			local base = m.a.cf0.Position.Y - O.Y
			local cf = CFrame.new(p + Vector3.new(0, base, 0))
			if dir.Magnitude > 0.1 then cf = CFrame.lookAt(cf.Position, cf.Position + (m.lie and -dir or dir)) end
			if m.lie then cf = cf * CFrame.Angles(math.rad(-90) * k, 0, 0) end
			m.a.root.CFrame = cf
			pose(m.n, (m.lie and "fall") or ((m.h or 0) > 0 and "jump") or "run")
		end
		if k >= 1 and m.proj then m.proj:Destroy(); objs[m.proj.Name] = nil end
		if k >= 1 then if not m.proj and not m.lie then pose(m.n, "idle") end table.remove(moves, i) end
	end
	-- fx
	for i = #fx, 1, -1 do local f = fx[i]; f[2] += dt * ts; local k = f[2] / 0.6; f[1].Size = Vector3.one * (2 + 22 * k); f[1].Transparency = k; if k >= 1 then f[1]:Destroy(); table.remove(fx, i) end end
	flash.BackgroundTransparency = math.min(1, flash.BackgroundTransparency + dt * 4)
	if hm.Visible then hm.Rotation += dt * 200 end
	-- camera
	local s = shotAt(st); if not s then return end
	local nxt; for _, x in ipairs(SHOTS) do if x[2] > s[2] then nxt = x; break end end
	local k = math.clamp((st - s[2]) / math.max(0.3, ((nxt and nxt[2]) or END) - s[2]), 0, 1)
	local pos, look, fov, roll
	if s[1] == "follow" then local o = objs[s[3]]; if o then pos = o.Position + s[4]; look = o.Position else pos = cam.CFrame.Position; look = pos + cam.CFrame.LookVector end; fov = s[5]
	else look = lookPos(s[4]); pos = (s[3] + O):Lerp(look, (s[6] or 0) * k); fov = s[5]; roll = s[7] end
	local sh = Vector3.zero
	if shake[1] > 0 then local u = (now - shake[2]) / shake[3]; if u < 1 then local a = shake[1] * (1 - u); sh = Vector3.new(math.noise(now * 30, 1) * a, math.noise(now * 30, 2) * a, 0) else shake[1] = 0 end end
	cam.CameraType = Enum.CameraType.Scriptable; cam.FieldOfView = fov
	cam.CFrame = CFrame.lookAt(pos + sh, look) * CFrame.Angles(0, 0, math.rad(roll or 0))
end)
-- ---------- start ----------
for n, a in pairs(TR) do a.root.CFrame = a.cf0 end
task.wait(1.5)
local f = Instance.new("Frame", gui); f.Size = UDim2.fromScale(1, 1); f.BackgroundColor3 = Color3.new(1, 1, 1); task.wait(0.1); f:Destroy()
print("ACTION START"); started = true
task.wait(END + 2); print("ACTION DONE")
