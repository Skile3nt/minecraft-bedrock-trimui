-- Host Lua test: actual menu/gamepad callbacks, no GPU or handheld claim.
local file = assert(io.open(arg[1]))
local source = file:read('*a'); file:close()
love = {event={quit=function() end}}
local api = assert(load(source .. [[
return {items=mainItems, credits=CREDITS, colors=COL, buttons=BTN,
        select=function(i) sel.main=i end, screen=function() return screen end,
        creditRow=function() return sel.credits end,
        seed=function() loadSettings(); versions={{name="fixture",tag="trusted",trusted=true}} end,
        profile=function() return selectedGameProfile end,
        launch=function() return launching end}
]]))()
local expected={'play','profile','versions','download','install','settings','backup',
                'selftest','controller_test','credits','exit'}
for i,item in ipairs(api.items()) do assert(item.id==expected[i], item.id) end
assert(#api.items()==#expected)
assert(api.colors.accent[1]==0 and api.colors.accent[2]==1 and api.colors.accent[3]==239/255)
assert(api.credits[1].title=='Minecraft Bedrock 1.16')
assert(api.credits[2].title=='Port & Adaptation: Skile')
api.select(10);love.gamepadpressed(nil,'b');assert(api.screen()=='credits')
love.gamepadpressed(nil,'dpdown');assert(api.creditRow()==2)
love.gamepadpressed(nil,'a');assert(api.screen()=='main')
api.seed();api.select(2)
assert(api.profile()=='NO_PARTICLES')
love.gamepadpressed(nil,'dpright');assert(api.profile()=='PERFORMANCE')
api.select(1);love.gamepadpressed(nil,'b')
assert(api.launch().name=='fixture' and api.launch().profile=='PERFORMANCE')
print('Host Lua: exact menu, Credits scrolling/back, profile and Play callbacks passed')
