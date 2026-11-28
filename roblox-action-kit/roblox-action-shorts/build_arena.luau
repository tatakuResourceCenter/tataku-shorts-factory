-- build_arena.luau : run once in Studio (Edit mode) through MCP execute_luau.
-- Builds workspace.ActionLab far from your map: green grid arena, castle wall, scaffold tower, crates, barrels,
-- and two R15 actors (Hero = teal ninja with red headband, Villain = black with glowing green eyes).
local O = Vector3.new(6000, 50, 0) -- far away so it never touches your game
local old = workspace:FindFirstChild("ActionLab"); if old then old:Destroy() end
local lab = Instance.new("Model"); lab.Name = "ActionLab"; lab:SetAttribute("Origin", O)
local arena = Instance.new("Folder", lab); arena.Name = "Arena"
local function P(sz, pos, col, mat, name)
	local p = Instance.new("Part"); p.Anchored = true; p.Size = sz; p.Position = O + pos; p.Color = col; p.Material = mat or Enum.Material.SmoothPlastic
	p.TopSurface = Enum.SurfaceType.Studs; p.Name = name or "P"; p.Parent = arena; return p
end
for ix = -3, 3 do for iz = -3, 3 do
	local c = ((ix + iz) % 2 == 0) and Color3.fromRGB(75, 190, 80) or Color3.fromRGB(95, 210, 95)
	P(Vector3.new(16, 1, 16), Vector3.new(ix * 16, -0.5, iz * 16), c, Enum.Material.Plastic, "Floor")
end end
for i = -3, 3 do
	P(Vector3.new(16, 14, 4), Vector3.new(i * 16, 7, -40), Color3.fromRGB(150, 150, 160), Enum.Material.Slate, "Wall")
	for j = 0, 3 do P(Vector3.new(3, 3, 4), Vector3.new(i * 16 - 6 + j * 4, 15.5, -40), Color3.fromRGB(150, 150, 160), Enum.Material.Slate, "Crenel") end
end
local Y = Color3.fromRGB(255, 200, 30)
for _, c in ipairs({ { -3, -3 }, { 3, -3 }, { -3, 3 }, { 3, 3 } }) do P(Vector3.new(0.8, 16, 0.8), Vector3.new(14 + c[1], 8, c[2]), Y, Enum.Material.Metal, "Pole") end
for h = 4, 12, 4 do P(Vector3.new(7, 0.4, 0.4), Vector3.new(14, h, -3), Y, Enum.Material.Metal); P(Vector3.new(7, 0.4, 0.4), Vector3.new(14, h, 3), Y, Enum.Material.Metal) end
P(Vector3.new(7.6, 0.6, 7.6), Vector3.new(14, 15.7, 0), Color3.fromRGB(120, 85, 55), Enum.Material.WoodPlanks, "Deck") -- tower top y = 16
for _, c in ipairs({ { 2, 6, 0 }, { 4, 7, 0 }, { 3, 6.5, 3 }, { -6, -6, 0 }, { -4, -7, 0 }, { -20, 8, 0 }, { 22, -14, 0 } }) do
	P(Vector3.new(4, 4, 4), Vector3.new(c[1], 2 + c[3], c[2]), Color3.fromRGB(170, 120, 70), Enum.Material.WoodPlanks, "Crate")
end
for i = 0, 2 do local b = P(Vector3.new(3.4, 3, 3), Vector3.new(8 + i * 1.2, 1.7, 1 + (i % 2) * 2), Color3.fromRGB(200, 40, 40), Enum.Material.Metal, "Barrel"); b.Shape = Enum.PartType.Cylinder; b.Orientation = Vector3.new(0, 0, 90) end

local actors = Instance.new("Folder", lab); actors.Name = "Actors"
local function mk(name, torso, limbs, head, pos)
	local d = Instance.new("HumanoidDescription")
	d.HeadColor = head; d.TorsoColor = torso; d.LeftArmColor = limbs; d.RightArmColor = limbs; d.LeftLegColor = limbs; d.RightLegColor = limbs
	-- To use a real avatar instead: d = game.Players:GetHumanoidDescriptionFromUserId(USER_ID)
	local m = game.Players:CreateHumanoidModelFromDescription(d, Enum.HumanoidRigType.R15)
	m.Name = name; m.Parent = actors; m:PivotTo(CFrame.new(O + pos + Vector3.new(0, 3, 0))); return m
end
local hero = mk("Hero", Color3.fromRGB(20, 170, 190), Color3.fromRGB(30, 30, 40), Color3.fromRGB(255, 220, 180), Vector3.new(12, 0, 6))
local vil = mk("Villain", Color3.fromRGB(20, 20, 24), Color3.fromRGB(20, 20, 24), Color3.fromRGB(30, 30, 34), Vector3.new(-14, 0, -2))
-- face each other
local hp, vp = hero:GetPivot().Position, vil:GetPivot().Position
hero:PivotTo(CFrame.lookAt(hp, Vector3.new(vp.X, hp.Y, vp.Z))); vil:PivotTo(CFrame.lookAt(vp, Vector3.new(hp.X, vp.Y, hp.Z)))
local function weld(part, to, cf) part.Anchored = false; part.CanCollide = false; part.CFrame = to.CFrame * cf
	local w = Instance.new("WeldConstraint"); w.Part0 = to; w.Part1 = part; w.Parent = part; part.Parent = to.Parent end
local band = Instance.new("Part"); band.Size = Vector3.new(1.25, 0.18, 1.25); band.Color = Color3.fromRGB(220, 30, 30); band.Material = Enum.Material.Fabric; weld(band, hero.Head, CFrame.new(0, 0.35, 0))
local tail = Instance.new("Part"); tail.Size = Vector3.new(0.2, 0.15, 1.0); tail.Color = band.Color; weld(tail, hero.Head, CFrame.new(0.2, 0.3, 0.8) * CFrame.Angles(0.3, 0, 0))
for _, x in ipairs({ -0.22, 0.22 }) do -- team color rule: villain = glowing green eyes (readable even in the dark)
	local e = Instance.new("Part"); e.Size = Vector3.new(0.22, 0.12, 0.05); e.Color = Color3.fromRGB(60, 255, 90); e.Material = Enum.Material.Neon; weld(e, vil.Head, CFrame.new(x, 0.1, -0.6))
end
lab.Parent = workspace
game.ReplicatedStorage:SetAttribute("ActionScene", true)
return "ActionLab ready"
