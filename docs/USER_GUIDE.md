# Uncle Farmer User Guide

Welcome to Uncle Farmer!

Uncle Farmer is a farming bot for Mist World. It helps your character travel to farming areas, fight monsters, manage supplies, and take care of routine tasks while you focus on something else.

Uncle Farmer uses NVDA as the game's default speech system. Important events and information are spoken through NVDA, and the program is designed to work with a screen reader.


## Table of Contents

- [What Uncle Farmer Does](#what-uncle-farmer-does)
- [Installing Uncle Farmer](#installing-uncle-farmer)
- [The Main Window](#the-main-window)
- [Plans](#plans)
- [The Farming Day](#the-farming-day)
- [Your Character](#your-character)
- [The Bag](#the-bag)
- [Fighting and Staying Alive](#fighting-and-staying-alive)
- [Tools](#tools)
- [Shard Prices](#shard-prices)
- [Shops and the Shard Market by Index](#shops-and-the-shard-market-by-index)
- [Every Other Menu](#every-other-menu)
- [Dungeons](#dungeons)
- [Walking](#walking)
- [Several Games at Once](#several-games-at-once)
- [Schedules](#schedules)
- [Results](#results)
- [The Game's Own Voice](#the-games-own-voice)
- [Quick Phrases and Teammates](#quick-phrases-and-teammates)
- [Chat](#chat)
- [Private Messages](#private-messages)
- [Updates](#updates)
- [The Game in Another Language](#the-game-in-another-language)
- [Contact](#contact)
- [Things to Know](#things-to-know)


## What Uncle Farmer Does

Uncle Farmer can:

- Travel to a farming map and fight monsters.
- Use potions when your character's HP gets low.
- Stop automatically when a rule you set is reached, such as a time limit, kill count, or low supply of potions.
- Read information directly from the game, including character positions, HP, your bag, and nearby monsters.
- Continue working while the game is in the background.

It does not require additional drivers or a virtual machine.

## Installing Uncle Farmer

Follow these steps to get started:

1. Extract the downloaded folder wherever you like, such as your Documents folder. Keep all the files and folders together.
2. Run `UncleFarmer.exe`. The first time you start it, Uncle Farmer offers to open Settings.
3. Open the **Game** tab in Settings. Select your Mist World folder (the one containing `mw.exe`), or start the game first and press **Find the running game**.
4. Press **Install**.
5. Restart Mist World.

That's it! Uncle Farmer is ready to use.

### About the game agent

Uncle Farmer installs an agent by adding one line to the game's `mw.exe.vmoptions` file. Before changing the file, it saves a backup named:

`mw.exe.vmoptions.bak-unclefarmer`

To remove the agent, use **Remove** in the same place in Settings. This removes the added line.

If you move the Uncle Farmer folder to another location, install the agent again so the game can find it.

### When the agent needs to be installed again

Sometimes the agent needs to be reinstalled. Uncle Farmer checks for this when it starts and explains why it needs attention.

For example:

- Another tool removed the agent's entry from the game's settings.
- The game is loading an agent from another Uncle Farmer installation, such as an older copy.
- The game was already open and started without the current version of the agent.

When this happens, Uncle Farmer offers to reinstall it.

- Press **OK** to close every open Mist World window and reinstall the agent. After that, start the game again. The game only loads the agent when it starts.
- Press **Cancel** to leave everything as it is.

If you press **Install** in Settings while a game is open, Uncle Farmer offers the same process.

## The Main Window

The main window has three tabs. You can switch between them using these keyboard shortcuts:

- **Ctrl+1 — Bot**
- **Ctrl+2 — Plans**
- **Ctrl+3 — Log**

### Bot tab

This is where you control your farming runs. It shows:

- Your open game windows.
- The plan selected for the character.
- The **Start** and **Stop** buttons.
- Live information about what the bot is doing and where it is.
- Your character's HP and MP.
- Your pet's HP and MP.
- Nearby players and their distance from you, measured in steps.
- Your bag contents, drop time, and kill count for the current run.

Each game in the Games list has its own menu. Select the game and press the **Applications** key or **Shift+F10**, or right-click it. The menu has three submenus:

- **Tools:** Gem Maker, Equipment Enhancer, Daily chores, Gathering, Dungeons, Sell the collection now, Sell shards now, Clean the bag now, Store items now, Restock now, and Update shard prices.
- **Character:** Settings, Bag and supplies, Scan now, Another character, Export character settings, and Import character settings. Fighting, pets, equipment choices and other character preferences stay inside their existing settings windows.
- **Run:** Start, Stop, Pause or go on, Stop every bot, Walk to a dungeon or map, Schedules, Results, and Speak the results.

Use the arrow keys to open a submenu, **Enter** to choose an action, and **Escape** to close it. The existing shortcuts, including **F5**, **F6**, **Ctrl+P** and **Ctrl+B**, also work without opening the menu. An entry that can't be used right now, such as a tool while that game's bot is running, is greyed out. Chat and private messages remain under **Messages** in the menu bar; mute and unmute remain under **Game**.

### Plans tab

This tab contains your plans and scripts. Select one to see a summary of what it does.

The **New plan** and **New script** buttons are on this tab. Everything else you can do with the selected plan or script is in its menu (**Applications** key, **Shift+F10**, or right-click): Run selected, Edit, Duplicate, Export, Delete, New plan, New script, and Import. You can also press **Enter** to edit it and **Delete** to delete it.

### Log tab

The Log tab shows what the bot has been doing. You can choose to see everything or only important events. To copy part of the log, select it and choose **Copy selection** from the log's menu (**Applications** key or right-click).

### Menus

The menu bar has these menus:

- **File:** Settings, the log and results folders, and Exit.
- **View:** The three tabs.
- **Game:** Mute and unmute this game or every game, and Open another game window.
- **Messages:** Private messages, Chat, and Let everyone get replies again.
- **Plans:** New plan, New script, Edit, Duplicate, Delete, and the **Import or export plans** submenu.
- **Help:** The quick guide, this user guide, keyboard shortcuts, the game and script guides, script commands, commands for trusted players, Check for updates, contact, the Telegram group, and About.

Entries that can't be used right now are greyed out. For example, Start is greyed out while the selected game's bot is running, and Duplicate needs a plan, not a script, to be selected.

**Tools**, **Character** and **Run** are in the selected game's context menu instead of the menu bar. References to these menu names elsewhere in this guide mean those submenus.

### Help and keyboard shortcuts

The **Help** menu provides two useful options:

- **Quick guide (F1):** Explains how to use Uncle Farmer step by step.
- **Keyboard shortcuts:** Lists the available keyboard commands.

### Starting and stopping the bot

The **Pause** key starts or stops the bot from anywhere, even while you are playing.

If you want to temporarily take control without ending the current run, use the **Pause** button on the Bot tab or press **F6**.

When paused, the bot releases all keys it is holding. You can then use Shift, Ctrl, and Alt normally in the game.

To continue the run, press **F6** again or use the same button, now labeled **Go on**. The bot continues from where it paused.

### Understanding the kill count

Uncle Farmer uses the game's own kill count.

A monster counts as a kill if one of your hits contributed to its death. This includes monsters killed by your area skills and monsters that another player finishes after you have hit them.

### Hourly farming report

While farming, Uncle Farmer reports once an hour how it spent its time.

The report breaks the time down into activities such as:

- Searching for monsters.
- Walking toward monsters.
- Selecting targets.
- Fighting.
- Resting.
- Travelling to town.

This can help you understand why a farming spot is producing fewer kills than expected. For example, a lot of searching combined with few kills may mean the area is crowded or the movement setting is not suitable for that map.

### Logs and troubleshooting files

Uncle Farmer saves its activity logs in the program's `logs` folder. It creates one log file per day.

If the program crashes, its error details are saved in `errors.log` in the same folder.

You can control how much information is written to the log files and how large they can grow in **Settings, Logging**. When the size limit is reached, the oldest logs are removed.

The Log tab always displays the current run's messages, regardless of your file logging settings.

Uncle Farmer also keeps two additional files to help diagnose startup and shutdown problems:

- `bootup.log` records each startup. It shows the settings, language, window, hotkeys, update check, and agent startup steps. Each step is marked as started and then done or failed, with an error when something goes wrong. The final line says whether startup completed successfully or which step failed.
- `teardown.log` records each shutdown. It tracks the bot shutdown process, message and chat readers, hotkeys, and timer. If a bot does not stop within five seconds, that is recorded too.

These files can help identify why Uncle Farmer refuses to open or gets stuck while closing.

The startup and shutdown logs are always written, regardless of the Logging settings. Like `errors.log`, they follow the same log rotation rules.

## Plans

A plan tells Uncle Farmer where to farm, when to stop, and where to go when the run ends. These three parts each have their own tab.

### Where to farm

Choose one or more farming spots. Each spot defines the map, movement style, and which monsters to target.

Press **Add** to add a spot. To change a spot, select it and press **Enter**, or open its menu (**Applications** key, **Shift+F10**, or right-click) for **Edit**, **Move up**, **Move down**, and **Remove**. **Delete** also removes it.

With one spot, Uncle Farmer stays there until the plan stops.

With several spots, it can either go around them in order repeatedly or visit each one once. Each spot has its own duration, which tells the bot how long to stay before moving to the next one.

**Movement**

You can choose between wandering randomly and following a patrol loop.

The short patrol loop is the quickest route that still passes within 40 steps of nearly every spot. It is especially useful in maze-like areas, such as Turkey Cave.

When following any patrol loop, the bot only goes after monsters that are within 40 walking steps. It leaves other monsters alone until the patrol brings it close to them.

### When to stop

You can set conditions that tell Uncle Farmer when to end a farming run. These include:

- A time limit.
- A specific clock time.
- A kill count.
- An item running low.

Some conditions are handled automatically through your character settings. These include:

- The game's drop time running out.
- Your bag becoming full.
- Reaching the last death you allow.
- Your gear breaking.
- Using up your last potion.

You can configure these character-related conditions in the character settings.

### Where to end

Choose where Uncle Farmer should take your character after the run ends. The available choices include:

- **Where the run started:** This is the default. If monsters spawn at the starting location, the bot chooses the nearest map without monsters instead.
- **A place you choose:** You can select a specific destination, choose **Where I stand now**, or choose a city square.
- **Home:** Use your hearthstone to return home.
- **The nearest map without monsters:** The bot finds a nearby map where monsters do not spawn.
- **Where it is:** The bot stays at its current location.

Every completed run follows the selected ending destination.

### Plans from older versions

Plans created with older versions of Uncle Farmer are converted automatically when opened in the new plan format.

For older plans, the duration of a single farming step becomes the plan's time limit. The plan is also set to return to the location where the run started.

## The farming day

Mist World's drop time resets at **00:00 GMT**, which is **05:00 in Pakistan**.

If you keep farming after the reset, you start using the next day's drop time. To prevent this, Uncle Farmer has a daily stopping time based on your computer's clock.

Every farming run stops at that time, regardless of the plan's settings or what the bot is currently doing. It then takes your character to the destination selected in the plan.

Uncle Farmer will not start another farming run between the daily stopping time and the game's drop-time reset.

You can change this time in **File → Settings → Farming day**.

By default, the daily stopping time is set to 10 minutes before the drop-time reset. In Pakistan, that means **04:50**. This gives your character some time to leave the farming area before the reset.

### After farming

The **Farming day** tab also lets you choose what Uncle Farmer should do after farming stops automatically.

This applies when a run ends because of the daily stopping time, the plan's time limit, exhausted drop time, a full bag, or the last death allowed.

It does not apply when you press **Stop** yourself. It also does not apply to runs that did not involve farming, such as Gem Maker, Equipment Enhancer, Walk to, `come`, or `follow`.

You can choose one of three actions:

- **Do nothing:** Leave the game running.
- **Close the game:** Close the game after farming ends.
- **Shut down the computer:** Wait until every running bot has finished and its game has closed, then shut down Windows.

When computer shutdown is selected, Uncle Farmer uses Windows' forced shutdown command:

`shutdown /s /f /t 60`

The 60-second delay gives you time to cancel the shutdown. Uncle Farmer announces the shutdown, and a window asks **Cancel the shutdown?** If you choose to cancel, Windows runs:

`shutdown /a`

## Your character

Uncle Farmer scans each character automatically. It detects the character's class, skills, keys, potions, fusion beasts, and pets.

Open **Character → Settings (Ctrl+P)** to choose how the bot handles your character. This is where you configure combat behavior, potions, fusion beasts, and pets. Key assignments and timing options are under **Advanced**.

### Skills

Open **Advanced → Skills** to see the skills found during the character scan. Each skill is listed with its assigned key and skill type.

For each skill, choose how the bot should handle it:

- **The bot decides** (default): The bot chooses when to use the skill.
- **Never:** The bot never uses the skill, assigns it to an empty key, or asks you to use it.
- **Only when HP is low:** The skill is saved for dangerous situations. This option is used for skills under the shield and defensive marks on the **Low HP** tab.
- **Whenever it's ready:** The bot uses the skill during fights as soon as its cooldown allows, before making its own skill choice. This is useful for skills the bot might otherwise leave unused, such as a stun.

The **Skills not in this list** setting controls what happens when you learn a new skill or assign a skill to a key later.

If you want the bot to use only the skills you have selected, set **Skills not in this list** to **Never**, then set the skills you want the bot to use to **The bot decides**.

### Other Advanced settings

The other tabs under **Advanced** contain more detailed options, including:

- How far the bot chases monsters while following a patrol loop.
- How far the bot stays away from bosses.
- When the character rests.
- When defensive skills, shields, and the healing skill are used.
- Which potions and Rice Rolls the pet uses.
- How the character travels, including walking, cable cars, airships, teleport skills, travel items, and VIP travel.
- Which keys are used for dialogs, discarding items, and the Action menu.

### How the bot chooses a route

When travelling, Uncle Farmer combines walking with cable cars and airships whenever using a ride makes the journey shorter.

For example, a journey from Giant Rock City to Tulip City might go underground to reach a cable car, then continue on foot after arriving.

The bot only plans to use a transport or airship when it can actually take it. Transports and airships must be enabled, and the character must have enough arnebia in the bag to pay the fare. VIP travel is free.

**Teleport skills.** A Mage's *Teleportation* takes the character to a city square, and an Elf's *Elven Teleportation* to the high-level lands such as Soul Burial Village or mist gods Ruins. When the character has one of these skills, the bot uses it whenever it makes the journey shorter. It costs only mana, never an item. You can switch it off in the profile: **Travel**, **Use the class's teleport skill (Mage, Elf)**.

When it teleports, the bot:

1. Walks out of the town first if it is standing in one. No skill works in a town's safe zone.
2. Deals with anything attacking it. Any hit breaks the 10-second channel.
3. Gets off the fusion beast.
4. Presses the skill's key and chooses the place from the game's list. If the skill is on no key, the bot puts it on an empty skill key, as it does for heals and buffs.

The first time, the bot learns which places this character's skill lists (the list grows with the skill's level) and remembers them. If something hits it during the channel, it fights back and tries again. After three broken tries it goes another way.

If those conditions are not met, the bot plans the route on foot instead.

The same rules are used when choosing the nearest shop or craftsman.

### Avoiding field bosses

Uncle Farmer recognizes field bosses by name. Its list includes Pig-Face Bat King, Man-wolf Caesar, Ice Queen Los, Cat King Carter, Pharaoh Tar, Elven King Erth, Fire Lord, Whale Monster Bigger, Monkey King, Barbarian Tyrant, Thunder Lord, Lich King, Meteor Queen Elsa, Dark Priest, Dracula, and other bosses in the same family, including their plain and Demonized forms.

The bot avoids attacking these bosses. It also avoids attacking anything within 40 steps of a recognized boss.

When a boss comes within that distance, the bot moves to the spot furthest away from it and then continues farming.

You can change the 40-step distance or turn boss avoidance off in **Advanced → Fighting**.

The game files do not tell the bot when a boss will appear. Instead, it reacts when it detects a boss nearby.

### Settings for each character

Every character has its own settings.

When Uncle Farmer encounters a character for the first time, it creates that character's settings using information from its initial scan.

## The bag

Open **Character → Bag and supplies (Ctrl+B)** to manage the items your character collects and the supplies it needs.

### Shards

For each shard, choose one of four actions:

- **Throw away**
- **Keep**
- **Store**
- **Sell**

If you have not assigned a shard to any of these lists, Uncle Farmer keeps it.

Shards marked **Throw away** are discarded right where your character is farming.

Shards marked **Store** or **Sell** are handled during a bag trip. If you want the bot to store or sell these shards, select **Sell and store by these lists** on the **Full bag** page.

To turn shards into gems, use **Tools, Gem Maker**.

### Other items

For items that are not shards, choose whether Uncle Farmer should:

- Keep them.
- Store them.
- Sell them.
- Throw them away.

### Supplies

Choose which potions and food Uncle Farmer should refill, and where it should get them.

### Full bag

Choose what Uncle Farmer should do when the bag becomes full. This page also includes the option to stop when the day's drop time runs out.

A full bag means the bag has reached its carrying limit. By default, the bot keeps farming until the load reaches that limit. It can also treat the bag as full if the load stops increasing just below the limit while monsters continue to die.

You can set a lower limit if you want the bot to stop or handle the bag before it reaches full capacity.

### Storing items now

Use **Store items now** in the game's menu in the Games list to move items to the storehouse according to your storage list.

The bot follows the rules under **Character → Bag and supplies → Move to storehouse**. It stores only the items on that list and keeps the required number of each item in your bag.

Items that are not on the list, or that belong to a different list, are left alone.

The bot walks to the nearest storehouse, using the same travel rules as a regular bag trip.

The log reports:

- Which items were stored.
- Which items were kept in the bag.
- Which listed items were not found in the bag.
- Which items the storehouse could not accept.

If the storehouse is full, anything that does not fit stays in your bag.

The storage list is read when the job starts. This means changes you make to the list before starting the job are applied.

### Triggers: jobs before and after farming

Open **Character, Settings, Triggers** to configure jobs that run before or after farming.

There are two lists, and both contain the same six jobs:

- **Sell shards:** Runs **Sell shards now** from the game's menu in the Games list. It sells the shards on your Sell list at the nearest Shard Market.
- **Clean the bag:** Runs **Clean the bag now** from the game's menu in the Games list. It throws away only the items on your throw-away list, right where your character is standing.
- **Update shard prices:** Runs **Update shard prices** from the game's menu in the Games list.
- **Gathering:** Runs the gathering task configured under **Tools, Gathering**.
- **Store items:** Runs **Store items now** from the game's menu in the Games list, following the storage list described above.
- **Restock supplies:** Runs **Restock now** from the game's menu in the Games list. It fills every supply that is switched on in **Character, Bag and supplies** up to its "fill up to" amount, from the storehouse first and then a shop, even when it is not yet down to its refill point.


## Fighting and staying alive

Uncle Farmer stands its ground and fights, even when several monsters attack at once. It does not turn its back on a group of monsters because they can keep following and attacking while it walks.

When several monsters are attacking and your HP is dropping, the bot uses your class's shields and powerful healing skills, as well as potions.

Damage-absorbing shields, such as Formless, can also be used while approaching or leaving a fight. They are not limited to the time spent attacking.

For melee characters, the bot prefers attacking a monster with fewer other monsters around it instead of jumping into the middle of a pack.

If no monsters are attacking but your HP is low, the bot rests before starting another fight.

While travelling, the bot only fights monsters that attack it.

### What counts as a monster?

Uncle Farmer follows the game's own target selection rules, the same rules used by the target key, **V**.

For example:

- Townsfolk, shopkeepers, and ducks or hens in towns are NPCs.
- Guards and summons belonging to other players are not treated as enemies.
- These characters and creatures are never attacked by the bot.

Before every fight, Uncle Farmer checks that the target key is set to enemies. If it is not, the bot switches it back.

When talking to an NPC, it switches the target setting to NPCs instead.

### Rage, marks, and combos

Warriors, Orcs, Hunters, and Assassins use the accumulation-points key, **T**, during fights. The bot presses it every one and a half seconds.

The game uses these accumulated points for abilities such as rage, marked targets, and combos. They can also affect fusion power and your pet's amiability.

The bot checks the available points before using skills that require them. For example:

- **Execute**, **Whirlwind Slash**, and **Battle Cry** are used only when enough rage is available.
- **Marked Shot** is used when at least two targets have marks. It requires at least three marks when there is only one target.

### Potions and deaths

When you use your last red or blue potion, Uncle Farmer stops the run and takes your character to the plan's ending destination.

There is one exception: if a restock rule can refill the potion, the bot can restock instead of stopping.

The bot also warns you when only 20 potions remain.

You can configure this behavior under **Character → Settings → Potions**.

**Stopping after deaths**

Under **Character → Settings → Fighting**, you can set how many deaths to allow before stopping.

After the last allowed death, the character first respawns in the city. Only after respawning does the bot stop the run, so your character is not left lying dead.

If you untick **Stop after too many deaths**, the bot never stops because of deaths. It respawns and returns to farming each time.

### Your own skills

Uncle Farmer reads the skills assigned to your character's keys. It checks both skill-key pages, including whichever keys you have chosen.

It also reads the game's skill descriptions to understand what each skill does.

The bot uses this information to help your character in several ways.

**Healing**

Sorceresses and Priests use their quick healing skills, such as Healing Wave or Heal, when their HP falls below 85%.

They can use these skills both during fights and between fights.

Red potions then act as a backup and are used only when HP falls below half.

**Buffs**

Long-lasting buffs, such as Strong-Arm Aura, Battle Cry, and Requiem, are kept active. The bot casts them again when they expire or when the game reports that they have been removed.

Shorter buffs, such as Bull's Eye, Scorch, and Winter Horn, are used to prepare for difficult fights and fights against groups of monsters.

**Removing debuffs**

The bot checks how many debuffs affect your character using the response to the **R** key.

If your class has a skill that can remove debuffs, such as Soul Purify, Holy Light, Purification, or Dispel Magic, the bot uses it.

Some debuffs cannot be removed by these skills. Poison is one example. The bot leaves those effects alone until something changes.

**Dangerous situations**

The bot treats these situations as dangerous:

- Your HP falls below half.
- Three or more monsters are attacking you while your HP is below 75%.

It responds in stages:

1. It first uses a shield that allows you to keep fighting, such as Formless, Ignore the Pain, Summon Spirit, or Ice Shield.
2. It then uses a powerful healing skill that can be cast immediately, such as Sorceress totems or a Priest's Light of Miracles.
3. When HP falls below 30%, a shield that prevents attacks is also acceptable, such as Turtle Guardian.
4. A shield that prevents movement, such as Ice Barrier or Soul of Redemption, is saved for the most dangerous situation: HP below 25%.

These skills are cast while standing still. The bot does not walk toward a monster just to use one of them.

### Combos

Some talents make one skill prepare the target for another skill. These combinations are called combos.

Uncle Farmer reads which talents you have activated. Each class has two talent paths that exclude each other, so a talent from the other path has no effect.

The bot uses the available combos when the skills involved are assigned to your keys.

You can see the detected combos in two places:

- At the beginning of a run, in the Log tab.
- In **Character → Overview**, after the character scan.

Here are some examples:

- **Cleave Combo:** Uses Sweep Attack immediately after Cleave.
- **Powerful Leap Attack:** Starts with Leap Slash, then immediately uses the next skill. The global cooldown is halved.
- **Ice Finger:** Uses Aqua Jet, then Ice Arrow to condense the target, followed by Ice Lance for three times its normal damage.
- **Ice combos without a talent:** Uses Ice Lance immediately after Frost Nova freezes the target. It also uses Ice Arrow instead of Magic Sphere because Ice Spikes increase Ice Lance's damage.
- **Freezing Cold:** Uses Ice Storm with its shorter cooldown.
- **Enhanced Explosion:** Applies Corrosion Spell to the target, then uses Skeleton Explosion, which always critically hits that target.
- **Divine Whip:** Keeps Mind Whip active on the target and uses Divine Nova while it is active.
- **Steady Hands:** Uses Aimed Shot just before Rapid Arrows or Marked Shot.
- **Ignition:** Uses Ignition after Pyroblast and Blazing Storm have built up three fire elements.

Some combos also depend on critical hits. These include Call of the Wilderness, Flame Combo, Crisp Wisdom, Wisdom, Dead Toxin Surge, Enrage, and Blazing Combo.

When a critical hit ends a skill's cooldown, the bot uses that skill next.

Critical-hit combos require **agent version 28 or newer**, which provides the bot with information about critical hits.

To disable these combinations, untick **Use the combos of the activated talents** under **Character → Settings → Fighting**.

### Empty keys

When a run starts, Uncle Farmer checks whether the skills and items it needs are assigned to keys.

This includes:

- The skills it uses.
- Your selected potions.
- The toolbox.
- The hearthstone.

If one of these is not assigned to a key, the bot can place it on an empty key.

An empty key is a key that has nothing assigned to it. This can be either:

- An empty skill key.
- An empty hotkey from **1** to **=**.

The game assigns skills through the skill panel using **Ctrl+Alt+key**. Items are assigned through the backpack using **Ctrl+number**.

The bot never overwrites a key that already has something assigned to it. This includes a hotkey that previously held a potion but is now empty because you ran out.

**Replacing used-up potions**

The bot also checks your keys while a run is in progress.

If the red or blue potion assigned to a hotkey runs out, or the game replaces it with something else, the bot checks whether your backpack still contains potions of that type.

If it finds more, it announces the change and assigns them to an empty hotkey between fights.

If no empty hotkey is available, the bot uses items directly from the backpack between fights.

**Missing skill keys**

The game can only cast skills assigned to skill keys.

If there is no empty skill key for a skill the bot needs, it cannot cast that skill. It tells you which skills are missing and identifies keys that repeat skills already assigned elsewhere, so you can decide what to change.

You can turn off this automatic key assignment behavior on the **Fighting** page.

### Repairs

When the game first warns that your equipment is about to break, Uncle Farmer repairs everything your character is wearing.

It uses one toolbox, choosing the cheapest type that can repair equipment at your level:

- **Small Toolbox:** Works up to level 60.
- **Large Toolbox:** Works up to level 80.
- **Alloy Toolbox:** Works at any level.

The bot does not use pliers.

If it does not know your character's level, it first reads the character sheet. If the level is still unknown, it uses an Alloy Toolbox.

**When a toolbox cannot repair everything**

Sometimes a toolbox cannot do the job. For example:

- The game refuses to use it.
- Its level limit is too low for your character.
- Some equipment remains broken after using it.

In these cases, the bot immediately tries the next stronger toolbox you carry.

If a toolbox is assigned to a hotkey from **1** to **=**, the bot uses it immediately, even during a fight.

If the toolbox is only in your backpack, the bot waits until the fight is over before using it.

If you have no toolbox, the bot tells you. If equipment is already broken and cannot be repaired, it moves to a safe location and stops.

You can configure repair behavior on the **Fighting** page under **Character, Settings**.

**About old equipment warnings**

Only warnings that appear while Uncle Farmer is running count as new repair warnings.

Mist World keeps the last warning for an item while the game remains open. This means a warning from an earlier run, when the equipment was already repaired, is ignored.

For example, running **Sell shards**, **Update shard prices**, or **Clean the bag now** will not waste a toolbox repairing equipment that is already fine.

However, if the game actually shows equipment as broken, Uncle Farmer repairs it immediately, regardless of when it broke.

### Fusion beasts and your pet in fights

**Fusion beasts**

Uncle Farmer waits until there has been no attack on your character or pet for six seconds before transforming into a fusion beast.

Every hit, or any decrease in your HP, restarts this six-second wait.

There is one exception: the bot does not delay getting off a Swift beast before fighting. Swift beasts prevent the use of skills, so the bot must leave that form when combat begins.

Sometimes the game refuses a transformation. When that happens, the bot continues without the beast and tries again later.

The retry intervals increase over time:

- After one minute.
- Then after two minutes.
- Then four minutes.
- This continues up to a maximum interval of ten minutes.

The walking assistant uses shorter retry intervals, starting at 15 seconds and increasing to one minute.

The Log tab reports the failed attempt and reports again when the beast is finally activated.

**Protecting your pet**

Uncle Farmer also monitors your pet's HP.

If the pet loses at least 2% of its HP within three seconds, the bot assumes that nearby monsters are attacking it. It prioritizes fighting those monsters, even if the game does not identify which monsters hit the pet.

There are two exceptions:

- A monster already attacking your character is finished first.
- A monster that is nearly dead is also finished first.

The bot stops treating nearby monsters as the pet's attackers once the pet's HP has remained unchanged for six seconds.

If the pet is out of sight or its HP cannot be read, the bot does not make assumptions about attacks on it.


## Tools

### Sound Silencer

Select a game and choose **Tools, Sound Silencer** from its context menu. The dialog directly shows
the numeric Sound ID input, Add button, Sounds and Muted Sounds lists, and Save button.
It uses the existing audio hook; no duplicate hook or live-listening subscription is installed.
The game can remain open while the dialog is open.

Add one available numeric ID at a time
(1–99999), then use right-click or Shift+F10 to **Move to Mute List**, **Move to Sounds List**,
**Rename**, or **Remove**. Named entries appear as `Background Music (1234)`; unnamed entries show
only their numeric ID. Optional names may be cleared; IDs and mute flags are preserved.
Duplicate IDs are rejected. All edits remain a draft until **Save**. Closing discards changes
since the last Save. Save stores both lists and names in settings.json and then applies the
saved mute rules, then closes after successful application, like the other tools. If saving or
application fails, the dialog stays open with its error and editable draft. If the game disconnects,
the choices are still saved and the dialog clearly
reports that live muting could not be confirmed. Disk-save failure leaves live audio unchanged.

Saved rules are app-wide and restore automatically when the app starts or a new game connects.
Scripts may change live muting afterward. Corrupt configuration is logged and does not silently
clear live mute rules. Existing audio lines use supported MUTE controls and subsequent signed-PCM
writes become silence; already-buffered audio without hardware MUTE may finish first.

Uncle Farmer includes several tools for tasks outside regular farming. You can run them manually from the **Tools** menu or use them in scripts.

Some tools can use craftsmen from your own gang, another gang, or the nearest city. Gang craftsmen are found in the **Outer Hall** of the gang's base, and their services cost less.

When using another gang's craftsmen, enter that gang's name.

All tools respect your arnebia reserve. They will not spend money that you have set aside.

Most tools also have a **Check only** option. This sends your character to the relevant NPCs, reads the actual prices and chances, and tells you what the tool would do. It does not spend anything or perform the task.

### Gem Maker

Open **Tools, Gem Maker** or press **Ctrl+G**.

The Gem Maker has two jobs.

**Make a gem**

Choose the gem, the level you want, and the quantity to make. You can also choose to make as many as possible.

The tool uses the gems and shards already in your bag. If it needs more Level 1 shards, it fetches them from your storehouse or buys them from the Shard Broker.

It collects shards in batches based on how much room is available in your bag. It respects your **Bag full at** setting.

The Shard Broker can sell no more than 2,000 shards in one purchase. The Gem Maker works out each batch using the available bag space and your spare arnebia. When collecting from the storehouse, it takes a bagful at a time.

**Make the most of my bag**

This job uses every shard in your bag to make gems. It then upgrades each gem colour as far as possible.

**When the job stops**

The Gem Maker continues until the job is complete or it cannot continue.

It tells you why it stopped. Possible reasons include:

- Your arnebia reserve would be reached.
- You have no protection runes left.
- There is nothing left to make.
- No more shards are available from the storehouse or Shard Broker.
- The Gem Craftsman fails to make anything for three rounds in a row, even though there are still combinations available.

A round that produces nothing because the game responds too slowly or the menu fails to open is retried. It does not count as a failed crafting round.

### Equipment Enhancer

Open **Tools, Equipment Enhancer** or press **Ctrl+Shift+E**.

The Equipment Enhancer improves your equipment to the level you choose, up to a maximum of **+12**. It uses protection runes during enhancement.

The tool also makes Enhance Crystals from crystal shards. It can get those shards from your storehouse or buy them from the Shard Broker.

Before enhancement begins, it prepares an initial stock of Enhance Crystals. It also prepares a fixed number of additional crystals whenever the current stock runs out.

### Daily chores

Open **Tools, Daily chores** or press **Ctrl+Shift+D**.

Daily chores handles tasks that each character can complete once per game day. The game's day starts at **00:00 GMT**.

Uncle Farmer keeps a record of completed chores. This prevents it from repeating a donation or another daily task if you run the tool again.

**Bank**

Deposits your bank income and the daily income from every Value Product card.

**Hunting bounties**

Collects hunting bounties from the nearest city officer who pays them.

**Pet rebirth**

Uses the free daily rebirths for the pet you choose.

The pet name found during the character scan should work, although the Pet Trainer may use a slightly different name for the same pet. For example, the character scan may identify a pet as **Eagle**, while the Pet Trainer calls it **Wild Eagle**.

Uncle Farmer never spends diamonds on pet rebirths.

**Gang**

Gang chores include the daily donation and daily construction.

For the donation, you can choose:

- 10,000 arnebia.
- 20,000 arnebia.
- 20 diamonds.

Arnebia donations still respect your reserve.

The game allows two construction jobs per day. Building and repairing share this same daily limit.

Construction does not cost anything. Each completed job gives gang contribution and gang points. It can also give arnebia depending on your rank. A general receives 3,000, 3,000, or 6,000 arnebia, depending on the construction.

You can choose where the construction takes place:

- **Inner Hall:** The East and West encampment reinforced constructions are available here. They are a short walk from the Gang Entrance.
- **Gang Highland:** The bot repairs the Crystal Turret and Wall barricade, then returns through the Teleportation circle.

Each gang has a different highland. Enter its number in the settings. You can find the number at the Highland Entrance under **Occupied Highlands**. For example, if your gang's highland is listed as **the own Gang's Highland 38**, enter `38`.

**Animal Shed**

Feeds your gang's breed beast once per day.

This gives:

- 500 gang contribution.
- 500 gang points.
- 2,000 arnebia.

Feeding the beast is separate from the two daily construction jobs.

**Secret room: sharing arnebia**

The secret room allows players to share arnebia. Sharing is available once during each half-hour period, at :00 and :30. You can do this five times per day, and both players receive arnebia.

Uncle Farmer handles the timing by entering shortly before the half-hour mark. For example, it may enter at 10:28, share, wait until 10:30, share again, and then leave.

While farming, the bot can handle this automatically. It leaves the farming area a few minutes before a half-hour sharing opportunity that has not yet been completed. The default is 10 minutes before, including travel time. It returns to farming afterwards and continues until all five daily shares are completed.

It tries to share with the players whose names you have entered first. If none of them are available, it can share with someone else in the room.

Practising in the secret room is a separate setting. This allows an assistant to kill monsters for you. It is set to zero minutes by default.

Remember that time spent in the secret room counts against your daily drop time in public areas.

**Check only and automatic chores**

The **Check only** option visits the relevant NPCs and reads their menus. It does not collect rewards, spend money, or enter the secret room.

You can also enable **At the start of the first farming run**. When enabled, Uncle Farmer performs the daily chores before the first farming run of each game day.

You can run daily chores from a script with these commands:

```text
chores
chores check
chores only=bank,donation
```

The first command runs the available chores. The second checks what the bot would do without performing the tasks. The third runs only the bank and donation chores.


### Gathering

Open **Tools, Gathering** or press **Ctrl+Shift+F**.

Gathering lets your character fish, mine, or collect herbs. Your character can learn one of these three gathering skills from the gang's Guru Elder or Master Pepper.

The Gathering window shows which skill was detected during the last character scan and its current rank, from **Newbie** to **Grand Master**.

#### Where to gather

Uncle Farmer checks gang gathering areas first, then moves on to places in the open world.

**Gang gathering areas**

Gang areas usually provide better gathering results than open-world locations. Their yield depends on the area's level and saturation.

The available areas are:

- Lake for fishing.
- Mining Area for mining.
- Herbal Garden for collecting herbs.

On the **Gangs** tab, add the gangs you want to visit and arrange them in the order you prefer.

You can add your own gang with **Add our own gang**. To add another gang, use **Add a gang by name** and enter its name. This is useful if you gather in a friend's or allied gang.

To change the order or take a gang off the list, select it and open its menu (**Applications** key, **Shift+F10**, or right-click): **Move up**, **Move down**, and **Remove**. **Delete** also removes it.

Uncle Farmer visits each gang in the order listed. For another gang, it first finds the gang through the Gang Entrance's **All gangs** list. It then enters the base and talks to the entrance to check the gathering area for your skill.

Before entering, the bot checks the area's level, saturation, and entry fee. It enters only if the fee is within your configured limit and paying it would not use your arnebia reserve.

Each gang's gathering area can be visited once per game day.

The game automatically sends your character outside after 30 minutes. Uncle Farmer then moves on to the next gang.

Because the game does not allow you to leave and resume the same gathering session, the bot sells your collected items before entering each gang area.

**Open-world gathering places**

After checking the gang areas, Uncle Farmer can gather at one of your saved places or at a known gathering location in the game.

To add your own location:

1. Travel to the exact spot where you normally fish, mine, or collect herbs.
2. Open the Gathering window.
3. Press **Add where I stand**.

Uncle Farmer saves that exact position and returns to it when gathering there.

To rename or remove a saved place, select it in **Your places** and open its menu (**Applications** key, **Shift+F10**, or right-click). Double-clicking a place also renames it, and **Delete** removes it.

You can also choose **The best for this character**. The bot then selects the highest-level gathering area where the monsters are no more than a few levels above your character. The default level difference is five.

If the game refuses to start gathering at a particular location, Uncle Farmer remembers that place and skips it until your gathering skill rank increases.

#### Starting and continuing gathering

Uncle Farmer starts gathering in the same way you would manually:

1. Open the backpack's **Profession skills** panel.
2. Press **Right Ctrl** on the gathering skill.
3. Choose **Start**.
4. Choose **Confirm**.

Once started, the game gathers automatically every two seconds. This continues until gathering is stopped or another skill or item is used.

In a gang gathering area, the bot lets the game handle gathering for the full 30-minute session.

In an open-world area, monsters can appear and attack your character. Uncle Farmer protects you throughout the session. It uses potions and healing skills, fights monsters that attack, returns to the saved gathering position, and starts gathering again.

#### Checking your bag before leaving

Before travelling to a gathering area, Uncle Farmer checks how much free space remains in your bag.

If there is less than 1,000 space available, it considers the bag too full to begin gathering.

A remaining space of 900 to 1,000 is considered safe. You can configure the selling behavior on the **Selling** tab.

If the bag is too full, the bot tells you and sells items first if selling is enabled. It only leaves once enough space is available.

This check is especially important for gang gathering areas. The bot cannot leave during the 30-minute session to sell items and then resume gathering.

#### Selling gathered items

When your bag becomes full while gathering outside a gang area, Uncle Farmer travels to the nearest suitable buyer:

- Aquaculture Buyer for fish.
- Ore Buyer for mining materials.
- Herb Buyer for herbs.

It sells the items and returns to the gathering location. Depending on your settings, it can stop instead of returning.

The bot sells everything the buyer accepts except items protected by your **Bag and supplies** settings. This includes items marked **Keep** and quantities you have chosen to keep.

It also sells gathered items once more when the gathering job ends.

#### When gathering stops

Gathering stops when your character runs out of Vitality for the day or when the configured time limit is reached.

Uncle Farmer never spends diamonds to refill Vitality.

For open-world gathering, you can also use **Stop when Vitality is down to** on the **When to stop** tab.

This setting tells the bot how much Vitality to save for later. It reads your current Vitality from the character sheet while gathering and will not start another trip if your Vitality is already at or below the selected amount.

#### Check only and selling manually

The **Check only** option reads the gang gathering area's entrance and tells you where Uncle Farmer would gather. It does not start gathering.

You can also use **Sell the collection now** in the game's menu in the Games list to sell gathered items to all three types of buyers from your current location.

In a script, use:

```text
gather
gather check
sell_collection
sell_collection fish
```

The first command starts gathering. The second checks what the bot would do. The last two sell your collection, with the final command specifying fish.


## Shard prices

Uncle Farmer keeps track of shard prices so it can estimate how much your collected shards are worth.

### Updating prices manually

To update shard prices through the Uncle Farmer window:

1. Open **Tools**.
2. Select **Update shard prices**.
3. Uncle Farmer travels to the nearest Shard Broker.
4. It reads the current shard prices from the broker's list.
5. It updates the saved prices in `data\shards.json`.

For each shard, Uncle Farmer checks whether the price in the broker's list matches the expected item and is a valid number.

- If the price is valid, the saved price is replaced with the newly read price.
- If the shard is missing or its price cannot be verified, its previous price is kept.
- The log explains which prices were updated and which were left unchanged.

The update only changes verified shard prices. It does not erase the entire price list or modify other data in the file.

### Updating prices with a script

You can also update shard prices by running this script command:

`update_shard_prices`

It performs the same update process: travels to the nearest Shard Broker, reads the current prices, and saves the prices it can verify.

### When Uncle Farmer is updated

An Uncle Farmer release may include a newer default shard price list. Installing the release updates the program's included data, but it does not automatically refresh the prices already saved by your copy.

After updating Uncle Farmer, run **Update shard prices** manually or use the `update_shard_prices` script command to read the current prices from the game again.

The saved prices are used by the bag manager and the Results window to estimate the value of collected shards.


## Shops and the Shard Market by index

Uncle Farmer can use item numbers to select entries in certain shop menus. This makes buying and selling faster and helps avoid mistakes when menus contain many items.

This feature is supported by agent version 53 and works with:

- Shard Broker menus for viewing, buying, and selling shards.
- Potion seller menus.

Uncle Farmer already knows how these menus are arranged in each city.

**How menu verification works**

Before selecting an item, the agent reads the menu currently displayed in the game and checks it against the menu layout it expects for that shop and city.

It verifies that:

- The menu contains the expected items.
- The items appear in the expected positions.
- The menu is for the correct action, such as buying or selling.

Only when the menu matches does the agent select an item using its number.

If the menu is different from what the agent expects, it refuses to select anything. This prevents it from accidentally choosing a different item because the menu has changed or the item positions are different.

After a menu has been verified, later selections can use item numbers without reading the entire list again. The agent still checks the full menu to make sure it is safe to continue.

**Other shops**

Shops that do not support indexed selection, such as the grocer, continue to use text-based item selection.

If an unexpected menu appears at the Shard Broker, Uncle Farmer selects nothing rather than risk buying or selling the wrong shard.


## Every other menu

For most game menus that support it, Uncle Farmer uses agent version 55 to select an entry directly by its text.

This applies to ordinary menus where the game presents a list of choices, such as NPC conversations and action menus. It does not replace the special indexed-selection system used by the Shard Broker and potion sellers.

**How direct selection works**

Instead of moving through the menu one entry at a time, the agent finds the requested entry by its text and selects it in a single step.

Before selecting, the agent checks that the menu currently displayed in the game matches what it expects. If the menu has changed or the requested entry is unavailable, it does not make an unsafe selection.

Direct selection also avoids having the game speak every menu entry while Uncle Farmer searches for the right one.

**If direct selection is unavailable**

If the game is using an older agent or the menu cannot be handled by direct selection, Uncle Farmer falls back to moving through the menu with the arrow keys.

It chooses the shortest direction to reach the requested entry. Since game menus wrap around, moving up past the first entry can sometimes be faster than moving down through the entire list.


## Dungeons

Ready for a dungeon run? Uncle Farmer can take your character into a daily dungeon, gather the supplies needed, and fight monsters for the full 15 minutes allowed by the game.

To get started, open **Tools → Dungeons** or press **Ctrl+Shift+G**.

### Which caves can you visit?

There are currently two caves available:

- **Spider Cave:** For characters at level 40 or higher. Its entrance is at Water Curtained Cave.
- **Scorpion Cave:** For characters at level 60 or higher. Its entrance is at Thousand Miles of Rivers.

You can enter only one dungeon per character each game day. That means visiting Spider Cave uses up your daily dungeon visit, so you cannot enter Scorpion Cave afterward on the same day.

Once inside, you have 15 minutes to defeat as many monsters as possible.

Caves for levels 80, 90, and 100 are planned for a future update.

### Choose your cave

Head to the **Caves** tab to choose where your character will go.

Not sure which cave to pick? Leave **The highest cave my level lets in** selected. This is the default option, and Uncle Farmer will choose the highest-level cave your character can enter.

You'll also see whether your character has already used its dungeon visit for the day.

Don't worry about accidentally entering a cave that's too difficult. Uncle Farmer checks your character's level and won't attempt to enter a cave above it. It will tell you if you cannot enter your selected cave.

### Get your supplies ready

Before heading out, make sure your character and pet have enough supplies. You can set the amounts in the **Supplies** tab.

These are the default amounts:

- Pet blue potions: 25
- Pet Rice Rolls: 3
- Your blue potions: 50
- Your red potions: 30

You can customize these amounts to suit your needs.

For potions, Uncle Farmer normally uses the one assigned to your character's hotkey. If no potion is assigned, it chooses the strongest available potion in your bag. You can also select a specific potion yourself.

Set an amount to `0` if you don't want Uncle Farmer to check or prepare that item.

**What if you're missing supplies?**

No need to visit the shop yourself. Uncle Farmer takes care of the preparation:

1. It checks your bag for the required supplies.
2. If anything is missing, it tries to take those items from your storehouse.
3. If you still don't have enough, it buys the missing items from a shop.

If you're still short after that, Uncle Farmer normally cancels the trip rather than sending your character into the dungeon unprepared.

You can choose to let it go anyway if you prefer.

One thing to remember: pet supplies are checked only when the pet option is enabled in **Character → Settings**.

### What happens during the dungeon run?

Once your supplies are ready, Uncle Farmer travels to the entrance and selects **Enter the dungeon**.

After your character reaches the safe landing area inside, the dungeon run begins. Uncle Farmer keeps your character moving and fighting until the visit ends. It won't stop to rest or leave for extra supplies.

**Finding monsters**

Uncle Farmer looks for the nearest monster it can reach within 90 walking steps. If it cannot find one within that distance, it follows its walking loop around the cave.

If your character fights from a distance, it can attack monsters as they come within range while moving. Once the game reports that a monster has been killed, Uncle Farmer moves on to the next target.

Monsters respawn approximately 30 seconds after being killed. They can appear anywhere in the cave, so keep exploring!

**Using your combat skills**

Uncle Farmer uses area skills when they can hit at least two monsters. You can increase this minimum if you want it to save those skills for larger groups.

It also checks the actual shape of each skill to work out which monsters it can hit:

- **Arc in front:** Multi Shot, Ice Storm, Fire Surge, and Holy Light Wave.
- **Straight ahead:** Sweep Attack and Flesh Cleave.
- **Ring around your character:** Whirlwind Slash, Frost Nova, and Divine Nova.
- **Area around the landing point:** Blizzard and Skeleton Explosion.

If your character attacks from a distance while moving, Uncle Farmer uses instant skills only. It avoids channeling skills because continuing to walk would interrupt them.

**Why does your character chase monsters farther?**

Dungeon runs use a chase distance of up to 90 steps. Regular farming normally uses 40 steps.

Tests using the actual cave layouts showed that the walking loop made little difference to the results. However, allowing casters to chase monsters up to 90 steps produced approximately 5–13% more kills.

**Taking care of your character and pet**

You don't need to worry about Uncle Farmer stopping for a rest. During the dungeon run, it uses potions instead of resting to keep your character's HP and MP up.

It also keeps your pet out and uses Rice Rolls to maintain its amiability.

If you haven't selected a pet in **Character → Settings**, Uncle Farmer looks after whichever pet is already out when the dungeon visit begins.

Remember, once your character enters the dungeon, it stays there for the full visit. Uncle Farmer won't leave early to restock supplies, empty a full bag, or visit a secret room. The game does not allow you to resume a dungeon visit after leaving.

### Your dungeon kill count

Wondering whether your pet's kills count toward your results? Yes!

Uncle Farmer includes your pet's kills in your character's kill count, just as the game does in its **Monsters Killed** report.

### When the dungeon visit ends

You don't have to watch the clock. After 15 minutes, the game normally moves your character out of the dungeon automatically.

If that doesn't happen for some reason, Uncle Farmer leaves through the game's **Action** menu.

After leaving, it follows your **Where to end** setting. You can choose to:

- Return to the place where the run started (the default).
- Go to a location you selected.
- Return home using a hearthstone.
- Stay where your character is.

### Check before you go

Want to make sure everything is ready before starting? Use the **Check** option.

It tells you which supplies are missing and which cave Uncle Farmer would choose. It does not enter the dungeon or use your daily visit.

**Using scripts**

You can also run the dungeon task through a script:

- `dungeon` — starts the dungeon task.
- `dungeon check` — checks your supplies and selected cave without entering.

You can choose where your character should go after the dungeon by putting `end_at` before the dungeon command in your script.


## Walking

Uncle Farmer has a walking tool that lets you travel to dungeon entrances and locations on the open-world map without starting a farming plan.

Open **Run → Walk to a dungeon or map**, or press **Ctrl+W**.

### Walking to a dungeon entrance

You can select a dungeon whose entrance NPC is known to Uncle Farmer.

An entrance may be a teleport circle or an NPC standing near the cave entrance.

Uncle Farmer walks your character to the entrance. You can also choose to have it open the NPC's menu when it arrives, so you can select the entrance yourself.

### Walking to a map or location

You can select any open-world map that your character can normally walk to and return from.

Closed maps and maps inside dungeons are not included.

You can also specify a particular cell on the selected map if you want to reach a more exact location.

### Showing the route

Enable **Show the route** if you want Uncle Farmer to speak the route before starting the journey.

During travel, Uncle Farmer uses your fastest available Swift fusion beast, including when passing through towns and areas with monsters.

It does not stop to fight monsters along the way, but it still uses potions to keep your character's HP up.

You can press **Pause** to stop the journey.

### Polson Wetland and its poison

Polson Wetland's poisoned ground hurts anyone on it, unless they have activated the General talent
Poison Immunity or are on a fusion beast (any kind). Without the talent:

- A trip through it (the only way to the Underground Water Cave and the sailing port beyond) gets on
  a fusion beast before stepping in and stays on it all the way across, without stopping to fight.
  Your fastest Swift beast goes on first, else your strongest Fierce one, whatever your travel beast
  setting says. If no beast will go on, it waits out a fight that just ended; if there's still none,
  the run stops before the step in, and the log says why.
- A trip that ends there (farming, gathering) goes, and says once that Poison Immunity isn't
  activated: every fight there is on foot, in the poison.
- Leaving Polson Wetland is never refused.

### Lava

The volcanic caves' lava lake and magma can be walked on, but a character standing in them loses
HP. The bot treats them as walls: it walks, stands and fights only on the islands and bridges. A
monster out in the lava is fought from the shore when it is within your attack's reach, and left
alone when it isn't. On the two maps where lava is the only way between parts of the map (Deep
underground and Demon Castle), it stays walkable.

## Several games at once

Have more than one Mist World character? You can run Uncle Farmer for several game windows at the same time.

You only need one copy of Uncle Farmer. It can manage multiple game windows, with a separate bot run for each character.

### Opening another game window

Uncle Farmer itself runs only once per Windows session. If you try to start it again, Windows brings the already-open Uncle Farmer window to the front instead of opening another copy.

To open another Mist World window, use **Game → Open another game window** or press **Ctrl+O**. You can also start Mist World again normally.

The agent supports multiple game windows. Each one needs approximately 1 GB of memory, so keep that in mind if your computer has limited RAM.

Each game window is named after its character, making it easier to tell them apart.

### Starting and controlling each character

Once your game windows are open:

1. Select a character's game in the **Games** list.
2. Choose the plan you want that character to follow.
3. Press **Start**.
4. Select another game window and repeat the process for the next character.

Each game window has its own bot run and operates independently.

For example, you can have one character farming while another is paused. Pressing **Pause** while working with one game affects only that game's bot. The other characters continue their runs without interruption.

The same applies when starting or pausing individual characters: you control each bot run separately through its corresponding game window.

### Stopping all bots

If you want to stop every bot at once, use **Run → Stop every bot** or press **Ctrl+Shift+S**.

This stops all active bot runs across your open game windows.

**A note about files**

While Uncle Farmer is running, it keeps its settings, plans, profiles, scripts, message files, and results open.

Windows may prevent you from moving or deleting these files while the program is using them. Close Uncle Farmer first if you need to manage or clean up those files manually.


## Schedules

Want Uncle Farmer to start farming without having to press **Start** yourself? You can use schedules to run a plan or script automatically at a time you choose.

Open **Run → Schedules** or press **Ctrl+Shift+H**.

### Setting up a schedule

You can schedule a task to run:

- **Once:** On a specific date and time.
- **Every day:** At the same time each day.
- **Selected weekdays:** On the days of the week you choose.

The schedule list shows when each task is due to run next and whether it is currently enabled.

The **Add** button creates a new schedule. The other options are in the selected schedule's menu (**Applications** key, **Shift+F10**, or right-click). You can also press **Enter** to edit a schedule and **Delete** to delete it.

- **Add:** Create a new schedule.
- **Edit:** Change the selected schedule.
- **Turn on or off:** Enable or disable a schedule.
- **Delete:** Remove a schedule.
- **History:** See what happened during previous scheduled runs.

Your schedules are saved in `schedules.json`, beside Uncle Farmer's settings. They are preserved when you update Uncle Farmer.

### What happens when a scheduled task starts?

A scheduled plan starts just as it would if you pressed the **Start** button yourself.

It uses the character's open game window and follows the same settings, including its plan, log, results, farming day, and ending location.

Each scheduled occurrence runs only once. If Uncle Farmer is closed or the schedule is turned off when its scheduled time arrives, that run is missed. It won't automatically try again later.

You can check the History to see when a scheduled run was missed.

### What if the game is busy or closed?

Uncle Farmer allows only one bot run at a time for each game window.

If the character's game is already busy with another run, or its game window isn't open, the schedule waits for up to 15 minutes.

If the game is still unavailable after that time, the scheduled run is skipped. The History records the reason.

A scheduled task will never stop an existing run just to make room for itself.

### Checking schedule history

The **History** section keeps a record of scheduled tasks, including:

- When each run was supposed to start.
- When it actually started, if it did.
- How it ended: finished, stopped, or encountered an error.
- The reason for a missed or skipped run.
- A summary line from the run's results.

This makes it easier to check whether your schedules are working as expected.


## Results

Curious about how your character did during the last farming run? The Results window gives you a closer look at everything Uncle Farmer has been keeping track of.

You can check your farming time, monsters defeated, items collected, earnings, expenses, and even combat statistics. It's a handy way to see how your character is progressing and where your resources are going.

Open **Run → Results** or press **Ctrl+R**.

### What does Uncle Farmer record?

Results are saved separately for each character. You can review:

- **Time and kills:** How long your character farmed and how many monsters were killed.
- **Contribution:** Your character's contribution.
- **Experience:** Experience gained and levels reached.
- **Arnebia:** Arnebia collected and earned from selling items.
- **Shards:** Every shard picked up, its estimated Shard Broker value, and how many were thrown away, sold, or stored.
- **Other items:** Items collected during farming.
- **Purchases and withdrawals:** Items bought from shops or taken from the storehouse.
- **Potions used:** The supplies consumed during the run.
- **Skills used:** Every skill your character cast, how many times, how much damage it did and its share of all your skills' damage, its critical hits and misses, and how much it healed. The skills that did the most damage come first.
- **Healing:** At the end, for classes that heal (such as Priests and Sorcerers): how much your own healing skills healed your character, your pet, and anyone else. Potions are not counted here.

Skills and healing are counted from this version on. Older runs show that they weren't counted.

You can choose which period to review:

- Current run (or the last one).
- Today.
- Yesterday.
- A day of my choice: pick any day with runs from the **Day** list, which shows each date, its weekday and how many days ago it was.
- Last 7 days.
- Last 30 days.
- All time.



### Understanding your farming time

The Results window shows two important time values.

**Time used**

This is the total time your character has spent actively farming, displayed in hours and minutes.

Time is not added while the bot is paused or performing a separate job instead of farming. For example:

- Time spent fighting monsters counts.
- Time spent paused does not count.
- Time spent performing a separate task, such as selling shards or cleaning the bag during a run, does not count.

This means the time used can be shorter than the actual time between starting and finishing a run.

**Time remaining**

This shows how much time is left before the run reaches its earliest applicable stopping limit.

Uncle Farmer checks three possible limits:

- **Plan's time limit:** The maximum duration you set for the plan, counted from when the run starts.
- **Plan's scheduled stop time:** The clock time you selected for the plan to stop. For example, if you set it to stop at 10:00 PM, Uncle Farmer stops when that time arrives.
- **Daily stop time:** The daily stopping time configured for your character. It prevents farming from continuing beyond your chosen daily limit.

Whichever limit is reached first determines when the run should end.

**How pauses affect the timers**

Pausing does not stop the stopping limits from counting down. Both the plan's time limit and clock-based limits continue to run, even though paused time is not included in **Time used**.

If no stopping limit is set, Uncle Farmer tells you. Once a run finishes, the remaining time shows `00:00`.

Both time values update while the Results window is open.

### Understanding your earnings

The Results window separates your farming income from the cost of supplies.

- **Earnings so far:** Arnebia collected from monsters or earned by selling items. This also includes earnings from Sell shards and Clean bag jobs performed during the run.
- **Total expenses:** The value of items consumed during the run, using their stored prices.
- **Net earnings:** Your earnings minus your expenses.

Buying an item does not immediately count as an expense. For example, buying a potion does not count as an expense until your character drinks it.

Money spent on shop purchases and travel fares is shown separately.

Older results saved by previous versions of Uncle Farmer recorded only the bag's net change in Arnebia. Earnings for those runs are calculated from that saved amount.

### Reviewing other jobs

Results can also show the work done by other tools.

Use **Show** to switch between:

- Farming.
- Gem Maker.
- Equipment Enhancer.
- Daily chores.

For these jobs, you can see what was made, what was used, and how much it cost.

These activities are kept separate from ordinary farming because, for example, shards turned into gems are not loot collected from monsters.

Jobs are also recorded separately when they run as part of a farming session. Daily chores are recorded before farming, while the `gem_maker` script command has its own results.

While a run is paused, nothing is counted as bot activity. Monsters you kill or items you collect manually during that time are not included in the bot's results.

### Understanding item expenses

Uncle Farmer can show you exactly how much your character spent on items that were consumed.

For each item, it records:

- The item's unit price.
- How many were used.
- The total cost.

It then adds these amounts to calculate the total expenses.

Prices come from different sources:

- **Shop items:** Their fixed prices from the game's data.
- **Shards:** The Shard Market prices most recently read by Uncle Farmer.

Shard prices can change, so their costs are estimates.

Remember that purchased items are not counted as consumed until they are actually used. If an item has no stored price, Uncle Farmer still lists it, but does not include it in the expense calculation.

Each run keeps the prices used for its calculations. Updating shard prices later will not change the expense figures in older results.

### Reviewing combat statistics

Uncle Farmer also records combat information reported by the game.

Depending on what the game provides, you can review:

- Damage dealt and damage received.
- Hits and misses.
- Critical hits.
- Defence breaks, including the best and most recent.
- Your best normal hit.
- The last monster killed.
- The monsters that dealt the most damage to you.

These statistics require agent version 28 or newer, the same version requirement used for crit-timed combos.

If the game does not provide a particular statistic, Uncle Farmer displays `null` for that value.

### Quick results and spoken summaries

You don't always need to open the Results window to check how things are going.

- Press **Shift+Pause** to hear a one-line summary of the game currently in front. You can do this from anywhere.
- Press **Ctrl+Shift+R** in Uncle Farmer to hear the same summary for the selected game.
- When a run ends, Uncle Farmer speaks a short summary automatically.

The summary starts with how long the character has farmed and how much of today's public area drop time is left, then the kills, contribution, experience and any level ups. For example: "farmed 2 h 15 min, drop time left 3 h 20 min, 340 kills, 4,183 contribution, 12,000 experience". The drop time comes from the character sheet; it is left out until the game has shown it. Damage and loot are in the Results window.

You can also change the spoken results settings to hear an update every few minutes or turn these announcements off.

All results are saved in the `results` folder, with a separate file for each character.


## The game's own voice

When Uncle Farmer is running, it can mute the game's speech so you can use your computer without hearing the game speak over other applications. Game sounds and music can still play.

The game can speak in different ways:

- **Screen reader:** The game sends text to its screen reader output, which is normally read by NVDA when NVDA is selected as the game's default speech system. Muting the game's speech stops this game output; it does not turn off NVDA or stop it from reading other applications.
- **SAPI:** Uses Windows Speech API voices to speak the game's messages. These are Windows text-to-speech voices.
- **Own voices:** Uses the voices built into Mist World instead of relying on a screen reader or Windows SAPI.

The **combat announcer** is another source of spoken information. It announces combat details, such as damage numbers. Uncle Farmer mutes these announcements along with the rest of the game's speech.

**Choose when to mute the game**

You can configure when Uncle Farmer mutes the game's speech:

- **While a bot runs:** Mutes the game only while your character is farming.
- **Always:** Keeps the game's speech muted whenever Uncle Farmer is running.
- **Never:** Leaves the game's speech alone.

**Mute or unmute a game manually**

You can also control speech for individual games:

- Press **Ctrl+M** to mute the selected game in the Games list.
- Press **Ctrl+U** to unmute it.
- Open the **Game** menu to mute or unmute every game at once.

If you manually mute a game, Uncle Farmer keeps it muted even after the farming run ends.


## Quick phrases and teammates

Quick phrases let you send frequently used messages without typing them every time. You can assign phrases to keyboard shortcuts and set them up separately for each character.

**Using quick phrases**

- Press **Shift+1** through **Shift+=** to send the phrase assigned to that shortcut.
- Press **Shift+Backspace** to configure your quick phrases.
- Each character has their own set of phrases.

Some phrases do more than send chat messages. Phrases beginning with certain control codes perform actions in the game instead. These controls are described in the game's help under **Quick Phrase Controls**.

**Quick phrase controls for teammates**

These special codes help your character find or coordinate with teammates:

- `/6` — Target the next teammate shown on the map.
- `/5` — Target whoever is attacking you.
- `/4` — Target whoever is attacking your current target.
- `/3` — Target whoever your current target is attacking.
- `/7` — Target the weakest teammate within 20 yards.
- `/8` — Target the weakest teammate within 30 yards.
- `/0`, `/1`, and `/2` — Set or cancel the team's navigation target.

At the beginning of a run, Uncle Farmer lists what each quick phrase does in the log. It does not display the actual phrase text there. You can also check the phrases under **Character → Scan**.

Uncle Farmer can add some missing control phrases automatically for certain character classes. For example, a Priest, Sorceress, or Witcher may need `/6`, `/5`, `/4`, or `/7`.

These phrases are added only to empty quick phrase slots. Existing phrases are never overwritten. This behavior is controlled by the `fill_empty_phrases` profile setting.

If you change this setting or update the phrases, restart the game so it can load the new agent.

**Finding and reaching teammates**

Uncle Farmer can also help your character locate teammates:

- It uses `/6` to get the map position of a teammate who is not currently visible.
- If your character is more than 20 yards away from the team leader and on the same map, Uncle Farmer can press **Shift+P** to teleport to the leader. It checks approximately every 50 seconds.

The `come` and `follow` commands can use these features when the target is leading the team.


## Chat

Uncle Farmer has a built-in chat window that lets you read and send game messages while your character is farming. Open it with **Messages → Chat** or press **Ctrl+T**.

Messages are sent through the game itself, so you can chat while the bot is running without interfering with its controls.

The Chat window has two tabs. Press **Ctrl+Tab** to switch between them.

### Channels

The Channels tab lets you read and send messages in the game's chat channels.

You can choose from:

- All
- Team
- Gang
- Nearby
- Map
- Global
- International
- Private channel
- Notices, which includes loot and event announcements

Press **Ctrl+1** through **Ctrl+9** to jump directly to a channel. Each channel also shows its unread message count.

Messages appear with the newest ones at the bottom.

To send a message, type it into the message field and press **Enter**. The field's label shows which channel will receive your message.

When **All** is selected, your message is sent to the same channel as the currently selected message.

### Private conversations

The second tab lets you read and send private messages.

It has two lists:

- **People:** Shows players you've chatted with, with the most recent conversations first. Unread message counts are also shown.
- **Messages:** Shows the conversation between you and the selected player, including messages you've typed directly in the game.

To send a private message, type it into the message field and press **Enter**.

**Starting a new conversation**

Use the **New chat with** field to enter a player's name or game ID, then press **Enter**.

You can also open its list with **Alt+Down Arrow** and select someone from:
- Players you've chatted with.
- Players currently visible in the game.

A player's name works if they are visible or if you've messaged them during the current session. A game ID works for any player.

### Replying to a message

Right-click a message in either chat tab, or select it and press **Shift+F10**, then choose
**Reply**. The message field gets the sender's `@username` prefix automatically. A reply preview
shows the original sender and message. Type your response and press **Send** or **Enter**.

The reply stays addressed to the original channel or private conversation even if new messages
arrive or you select another conversation. Selecting Reply repeatedly does not duplicate the
prefix. **Cancel reply** or **Escape** cancels reply mode and keeps the body of your draft. If
sending fails, the draft and reply target remain available for retry. Messages without a sender,
such as notices, cannot be replied to.

### Chat filters

Right-click a message and choose **Add to filter list** to hide messages with exactly that text.
The rule is saved immediately. Matching uses the message body, without its sender, channel or
displayed timestamp, and applies across all games' Chat windows.

Open **Chat filters** from either chat tab to manage rules:

- **Filter list** shows hidden messages still in the current game's chat buffers and the rules
  responsible for hiding each one. **Restore selected message** disables all rules matching it;
  other messages hidden by those rules also return when you save.
- **Filter settings** lets you add, edit, delete, enable and disable rules. Changes in this
  window apply only when you press **Save**; cancelling leaves the saved rules unchanged.
- **Exact message** matches the complete body. **Contains text** matches a word, phrase or
  sentence anywhere in it. **Wildcard** matches a complete pattern: `*` matches any number of
  characters and `?` matches one character. For example, `*hello*` matches any body containing
  `hello`. Patterns are not regular expressions.
- **Match case** controls whether uppercase and lowercase differ. **Test filter** in the editor
  checks a sample message without changing chat or saving the rule.

Filtering changes only what the Chat message lists show. Delivery, voice messages, speech,
notification tones and automatic private-message handling continue normally. No messages are
deleted by a filter. Rules, including their text or patterns, are saved in application settings
and survive restarts; the chat history itself remains in memory. Old messages that have already
left the existing bounded chat buffers cannot be restored.

### Voice messages

You can record and send voice messages from either tab using the buttons beside **Send**.

When a voice message arrives, it appears as a message marked **voice message**.

- Press **Alt+Y** or **Enter** to play a selected voice message.
- Press **Alt+V** to start recording using the game's microphone.
- Press **Alt+V** again to stop recording and send the message.
- Press **Escape** while recording to discard it.

The game supports voice messages only in Team, Gang, and private conversations. The voice message button indicates when the selected channel does not support them.

**Voice message processing**

Uncle Farmer improves recorded audio before sending it:

- Removes background hum and silence.
- Adjusts the volume to make it more consistent.
- Sends audio at twice the game's usual quality, using the game's own sound format.

Each voice message can be up to 20 seconds long. Longer recordings are divided into smaller messages of similar length. For example, a 45-second recording becomes three 15-second messages, sent one after another.

Recording stops automatically after five minutes.

Voice messages require agent version 42 or newer. Restart the game after updating the agent.

**A game playback issue**

There is a known game issue that can affect voice messages when two game windows are open. One game may play all voice messages too slowly, making the voices sound unusually deep.

Agent version 51 fixes this issue.

If you prefer to keep the game's original deep voice playback, open **File → Settings → Speech and language** and untick **Fix the speed of voice messages the game plays by itself**.

Every open game window plays voice messages as the game normally would. You can turn the setting back on at any time; restarting the game is not required.

### Chat and speech settings

You can choose when Uncle Farmer reads new messages aloud:

- **Only when Chat is open:** Reads messages only while the Chat window is open. This is the default.
- **Always:** Reads new messages even when Chat is closed.
- **Never:** Does not read new messages aloud.

You can also choose which channels are read aloud. Team, Gang, and Nearby are enabled by default.

**Message tones**

You can use different notification tones for trusted players and everyone else. You can also choose not to play a tone.

Private message readouts follow your configured speech settings.

### Message sending limits

**Message timestamps**

You can choose whether to show the time after each message. If timestamps are enabled, you can use either a 24-hour or 12-hour clock.

The game limits how quickly messages can be sent:

- One message line every two seconds.
- Three seconds between messages in Global chat.

These limits apply to all channels and private messages together.

Uncle Farmer manages a message queue for chat messages, automatic replies, and responses to trusted players. It also accounts for messages you type directly in the game.

If the game drops a message because it was sent too quickly, Uncle Farmer tries sending it again. Messages are limited to 200 characters and are split at spaces when necessary.

### When the game window is active

When a game's own window is in the foreground, Uncle Farmer does not read incoming messages aloud or play notification tones. You can still see the messages in the log and Chat window.

### Chat history

Chat messages are not saved to files. Uncle Farmer keeps them in memory only while the application is running. Closing Uncle Farmer clears this chat history.


## Private messages

Uncle Farmer can automatically reply to private messages while your character is farming. You can also mark certain players as trusted so they can send commands to control your bot.

Open **Messages → Private messages** or press **Ctrl+Shift+M**.

### Automatic replies to strangers

When someone who is not on your trusted list sends a private message, Uncle Farmer can reply automatically.

It sends a few replies at a time, choosing from the messages you've configured. It does not repeat the same reply twice in a row.

After sending its replies, Uncle Farmer sends a goodbye message and stops responding to that player for one hour.

You can edit the replies to use your own wording. The default messages are polite responses that let people know you're away.

**Using a player's name in replies**

You can include `{name}` in a reply. Uncle Farmer replaces it with the sender's name.

There is also a **Call them by their name** option. When enabled, Uncle Farmer adds the sender's name to the beginning of a reply that does not already contain `{name}`.

### Trusted players

You can add trusted players using either their character name or game ID. Both types of entries can be mixed in the same list.

Trusted players can use commands to check information or control your character. Their messages are handled according to your configured speech settings.

Trusted players do not receive the automatic replies intended for strangers.

**When the game window is in front**

When a game's own window is in the foreground, you handle private messages yourself. Uncle Farmer does not read them aloud or play notification tones, but the messages still appear in the log and Chat window.

Uncle Farmer also does not send an automatic away reply while the game window is in front.

Trusted commands can still work in this situation unless **Take their commands while game window is in front** is disabled.

### Commands from trusted players

Trusted players can send commands by private message. The command must be sent as the whole message.

Available commands include:

- `help` — Lists available commands.
- `help follow` — Explains the `follow` command.
- `status` — Checks the bot's current status.
- `where` — Checks your character's location.
- `players` or `who` — Lists nearby players, starting with the nearest.
- `pet` — Reports your pet's HP and MP.
- `leader` — Makes the trusted player the team leader.
- `results` — Gets farming results.
- `today` — Gets today's information.
- `bag` — Checks your character's bag.
- `drop` — Checks drop information.
- `pause` — Pauses the bot.
- `resume` — Resumes the bot.
- `stop` — Stops the current run.
- `start [plan]` — Starts farming, optionally using the named plan.
- `home` — Sends your character home.
- `come` — Sends your character to the trusted player.
- `follow` — Follows the trusted player.
- `unfollow` — Stops following.
- `buff` — Enables buffs while following.
- `add` — Accepts a team application.
- `leave`, `quit`, or `quit team` — Leaves the team.
- `mute` — Mutes the game.
- `unmute` — Unmutes the game.
- `quit game` — Closes the game.

Send `help` to see the available commands. You can also send `help` followed by a command name for more information.

Uncle Farmer automatically accepts team invitations from trusted players. It declines invitations from other players by pressing **Escape** while the bot is running.

### Using `come`

The `come` command sends your character to the trusted player.

How it works depends on whether Uncle Farmer knows the player's location:

- If the player is one of your characters running in the same Uncle Farmer session, it can use their exact location.
- Otherwise, it uses the player's last known location from any game, provided that location is no more than 10 minutes old.

For more accurate directions, send `come` together with the player's location. You can copy a location from the game using **E**, followed by **Shift+C**. This includes the map and coordinates.

You can also send `come` followed by a map name.

Your character stops farming, travels to the target, and waits nearby. If it is already following someone, `come` simply helps it close the distance.

### Using `follow`

The `follow` command makes your character stay with a trusted player.

Your character will:

- Move closer when the player gets too far away.
- Fight monsters attacking your character.
- Help fight nearby monsters that the player is fighting.
- Follow the player when they change maps.

For your own characters, Uncle Farmer can follow them anywhere. For other players, it uses the map exits to travel between maps.

Starting `follow` stops the current farming run. If Uncle Farmer cannot find any sign of the target for one minute, it stops following.

**Buffs while following**

Buffs are disabled by default while following someone. Healing, shields, and dispels can still be used.

- Send `buff` to enable buffs for the rest of the follow session.
- Send `buff off` to disable them again.

Every new follow session starts with buffs disabled.

### Stopping follow

Send `unfollow` to stop following the player.


## Updates

Uncle Farmer can check GitHub for newer versions and help you install them.

When a new version is available, it shows the release notes so you can review what's changed before deciding whether to update.

You can also check manually through **Help → Check for updates**.

### Installing an update

When you accept an update, Uncle Farmer handles the download and installation for you.

The process works as follows:

1. **Download:** Uncle Farmer downloads the new version from GitHub.
2. **Verify:** It checks the downloaded files before installing them.
3. **Close the games:** If any Mist World windows are open, Uncle Farmer asks for confirmation before closing them. This is necessary because the game loads the Uncle Farmer agent when it starts. The agent is a component that allows Uncle Farmer to interact with the game, and it must be replaced along with the application.
4. **Install:** Uncle Farmer installs the downloaded version and restarts itself.
5. **Start playing again:** Once the update is complete, you can open Mist World again. The game will load the updated agent.

The update process does not send your personal or game information to GitHub.

### Update settings

Open **File → Settings → Updater** to manage update options.

Here you can:

- Check your currently installed version.
- See the source of the current version.
- Enable or disable the startup update check.
- Choose a release channel.
- Ask Uncle Farmer to offer a version again if you previously declined it.
- Save your settings and check for updates immediately.

The **Look for a new version when Uncle Farmer starts** option controls whether Uncle Farmer checks GitHub each time it starts.

### Choosing a release channel

Uncle Farmer offers two release channels:

- **Master:** The stable release channel. This is the default and contains the hand-made releases also listed in the README.
- **Dev:** The development channel. It offers builds made from the `dev` branch whenever changes are pushed to GitHub.

Dev builds let you try newer changes sooner, but they may contain bugs or unfinished features.

A development version includes its build number in the version name. For example, `0.9.0-dev.57` means the 57th development build after version `0.9.0`.

Each channel offers only its own releases.

If you switch from Dev back to Master, Uncle Farmer keeps your current development version until a newer stable release is available. To return to the stable version immediately, download the stable release ZIP and unpack it over your existing Uncle Farmer folder.

### What happens to update files?

During an update, Uncle Farmer downloads and unpacks files into an `update` folder beside the application.

After the update succeeds, fails, or is cancelled, Uncle Farmer removes the temporary update files and cleans up that folder.

This cleanup affects only the `update` folder. It does not delete your profiles, plans, settings, or other personal data.

Update activity is recorded in `logs/update.log`.

### Updating manually

You can also install an update yourself:

1. Close Uncle Farmer and all Mist World game windows.
2. Download the newer `UncleFarmer-<version>.zip` file.
3. Unpack it over your existing Uncle Farmer folder.

Your existing user data is preserved.

After updating, check **What's new.txt** to see what has changed.


## The game in another language

Uncle Farmer works with any of the game's language packs, using `language\lang.txt`, not just English. It reads the same language files as the game and translates what it sees back into English. This helps it recognize the same potions, skills, monsters, pets, and menus regardless of the selected language.

Anything the language pack leaves untranslated is already in English. Player names are never changed.

**Changing the game language**

To use another language:

1. Choose your preferred language in Mist World.
2. Restart the game so the new language settings take effect.

Uncle Farmer will then read the language files for the selected language.


## Contact

Need help, found a bug, or have a suggestion? Uncle Farmer provides a couple of ways to get in touch.

### Contact the developer

Open **Help → Contact the developer** to see the developer's email address.

The window provides buttons to write an email or copy the address so you can contact the developer using your preferred email application.

If you're reporting a bug, opening an issue on GitHub is usually the best way to share the details and help track the problem.

### Join the Telegram group

You can also join the Uncle Farmer Telegram group to connect with other users.

Open **Help → Join Telegram group**, or use the link below:

[Join the Uncle Farmer Telegram group](https://t.me/+55NtoqsY7u1lMzNk)


## Things to know

Here are a few extra details that can help you maintain Uncle Farmer, protect your settings, and contribute translations.

### When Uncle Farmer cannot find the game

Some tools that clean or modify Mist World settings, such as `mwMod`, may remove the line that loads the Uncle Farmer agent.

If this happens, Uncle Farmer may no longer recognize the game.

To fix it:

1. Restart Uncle Farmer.
2. If it offers to reinstall the agent, accept.
3. If it does not, open **File → Settings → Install** and install the agent manually.
4. Restart Mist World so it loads the agent again.

### Backing up your settings

Your character settings, farming plans, scripts, and logs are stored in separate folders beside the application:

- `profiles` — Character settings and profiles.
- `plans` — Your saved farming plans.
- `scripts` — Scripts used by Uncle Farmer.
- `logs` — Log files.

You can copy these folders to another location to keep a backup. This is especially useful before making major changes or moving Uncle Farmer to another computer.

### Creating a translation

If you'd like to translate Uncle Farmer into another language, you can start with the provided translation template.

1. Open the `lang` folder.
2. Copy `unclefarmer.pot`.
3. Rename the copy using your language code, such as `fr.po` for French.
4. Open the new `.po` file in a translation editor or text editor.
5. Fill in the `msgstr` entries with your translations.
6. Run the following command from the project folder:

   `uv run python -m unclefarmer --strings`

Your translation should then appear in Uncle Farmer's **Settings → Language** list.

### Urdu translation

Uncle Farmer includes an Urdu translation in `lang\ur.po`.

It uses Roman Urdu, meaning Urdu written with Latin letters rather than the Urdu or Nastaliq script.

Uncle Farmer also keeps wx in English left-to-right mode, so its interface does not switch to a right-to-left layout.


### Reacting to sounds in scripts

`sound_watch <ids>` changes the game's global watch filter. `sound_mute <ids>` changes its mute
filter. Both persist until changed or the game exits. `sound_wait <ids> timeout=30` waits for a
new matching request and keeps Stop/Pause responsive. It uses a temporary connection subscription,
so it does not replace other sound listeners. A timeout sets `sound_received`
to false. Missing positions set `sound_positioned` to false.

```text
sound_wait 1000-1010 timeout=30
if sound_received
    say Sound {sound_id} requested
    if sound_positioned
        say Position {sound_x}, {sound_y}
    end
end
```

Use IDs observed in your game; the IDs above are an example. `sound_muted` describes muting at
request time. These commands observe requests, not proof that audio reached the speakers.
For sounds already playing, supported MUTE controls are changed immediately. The PCM hook also
silences subsequent signed-PCM writes without changing the game's sample buffer. Audio already
buffered in a device without a MUTE control may finish before silence begins.
