# Writing scripts: a guide

Ever wished your character could do more than just farm in one place? Maybe you want to visit different maps, restock your potions when supplies run low, or keep farming until you've collected enough items.

That's what scripts are for!

A **plan** handles ordinary farming: choose maps, set how long to farm, and add rules for when to stop. A **script** gives you more freedom. It's a list of commands that Uncle Farmer follows from top to bottom. You can make decisions, repeat tasks, visit shops between farming sessions, and react to what's happening in the game.

And here's the good news: **you don't need to be a programmer to write one.** If you can write a shopping list or follow a set of instructions, you're already familiar with the basic idea.

We'll start with something small and gradually build up to more powerful scripts. Every example in this guide can be copied directly into the script editor, so feel free to experiment as you learn.


## Sign in before a script

Put `login` as the first command in a scheduled script: the schedule's selected character supplies the identity. `login "Character - S1"` is also available when the script itself should name the character. If that character is already in the selected game, Uncle Farmer uses it. Otherwise it uses one signed-out game; when there is none, it opens one game window, waits for its agent, then uses the saved sign-in and the real character list to select the matching character ID. The address is learned when the character is first seen and is shown read-only in Character Settings, Overview; no password is stored. The command stops safely if the character has not been seen before, its saved account is unavailable, or more than one game is signed out.

## 1. Your first script

Let's get your first script running! We'll start with a simple task: travel to a farming map, fight monsters for ten minutes, and then return home.

**Creating your script**

1. Open the **Plans** tab and press **New script**.
2. Give your script a name, such as `My first script`.
3. Replace the example text with these three lines:

        travel "Wolf Prairie"
        farm minutes=10
        hearthstone

4. Press **F5** to check your script. If you see "The script reads correctly", Uncle Farmer has understood every line.
5. Press **Ctrl+S** to save your script, then press Escape to close the editor.
6. On the **Bot** tab, choose `My first script (script)` in the Plan box and press **Start**.

**What will happen?**

Uncle Farmer follows the commands in order:

- `travel "Wolf Prairie"` sends your character to Wolf Prairie.
- `farm minutes=10` starts farming and stops after ten minutes.
- `hearthstone` sends your character home.

That's it! You've just created and run your first script.

It might be short, but you've already learned the most important idea behind scripting: give the bot a series of instructions, and it follows them one by one.


## 2. The rules of writing

Before we start making scripts do interesting things, let's get familiar with a few simple rules. Don't worry, there aren't many!

**One command per line**

Each line contains one command. The first word tells Uncle Farmer what to do, and the rest provides the details.

For example:

    travel "Wolf Prairie"
    farm minutes=30
    hearthstone

The bot reads these commands from top to bottom, one line at a time.

**Add notes with `#`**

You can leave yourself reminders or explanations inside a script. Start a note with `#`, and Uncle Farmer will ignore everything after it on that line.

    # Farm the wolves before dinner
    farm minutes=30    # Half an hour should be enough

Notes are useful when a script gets longer or when you want to remember why you added a particular command.

**Put names with spaces in quotes**

If a map, item, or other name contains spaces, wrap it in quotation marks.

    travel "Wolf Prairie"

Names containing only one word don't need quotation marks.

**Uppercase and lowercase don't matter**

Commands aren't case-sensitive. That means `Farm`, `farm`, and `FARM` all mean the same thing.

Choose whichever style you find easiest to read. The examples in this guide use lowercase commands.

**Use indentation to keep things tidy**

Spaces at the beginning of a line are ignored by the bot. However, indentation makes it easier to see which commands belong together.

For example:

    repeat
      farm minutes=30
      hearthstone
    end

The two spaces before the commands inside `repeat` are there for readability. You can use indentation to make longer scripts easier to follow.

**Close your blocks with `end`**

Some commands, such as `repeat`, `if`, and `while`, can contain other commands underneath them. These groups of commands are called **blocks**.

Every block needs a matching `end` to tell Uncle Farmer where that group finishes.

    repeat
      farm minutes=30
      say farming session finished
    end

Think of `end` as the closing marker for a group of instructions. Without it, the bot won't know where the block finishes.

That's all you need to know about the basic writing rules. With these in place, you're ready to start giving your character more interesting instructions!


## 3. Going places

Before your character can start farming, they need to get somewhere! Uncle Farmer has two commands for traveling: `travel` and `go`.

Both can take your character to different maps, but they work a little differently.

### Using `travel`

The `travel` command works out the entire route for you. It can handle walking, cable cars, airships, and teleport circles.

Here are the available forms:

    travel <map>                 go to a map from anywhere
    travel <map> at <x>,<y>      go to a map and to a cell on it
    walk <x> <y>                 walk to a cell on the map you're on

You can identify a map by its name or its number.

For example:

    travel "Orcus Tribe"
    travel 5301
    travel "central plains" at 220,215

The last example takes your character to a specific cell on the map instead of simply arriving somewhere on it.

### What if two maps have the same name?

Some maps share names. If Uncle Farmer chooses the wrong one, use the map number instead.

You can find each map's number in brackets in the map list inside the plan editor.

### Using `go`

The `go` command uses the same walking assistant available in the main window:

**Run → Walk to**, or press **Ctrl+W**.

It follows the same route as `travel`, but there's an important difference: your character rides their fastest Swift fusion beast for the entire journey.

That includes towns and areas filled with monsters. Your character won't stop to fight along the way. Potions still keep your HP up, so the journey can continue without getting distracted by battles.

Here are the available forms:

    go <map> [at <x>,<y>]              go to a map (and a cell on it)
    go <map> at <x>,<y> to <npc>       go to a map and walk up to an NPC standing near x,y
    go dungeon <name>                  walk up to a dungeon's entrance NPC
    go dungeon <name> talk             ...and open its menu there

For example:

    go dungeon "Nether Cave" talk
    go "Lifting Platform No. 1" at 10,75 to "Nether Cave"

The first example takes your character to the entrance of Nether Cave and opens the NPC's menu.

The second takes your character to Lifting Platform No. 1, then walks up to the NPC named Nether Cave near the specified coordinates.

### Finding dungeon entrances

Uncle Farmer keeps a list of the dungeons it knows about. You can find this list in the **Walk to** window, including dungeons whose entrances haven't yet been seen in the game.

This makes it easier to send your character to a dungeon entrance without having to work out the route yourself.

Whether you're heading to a farming map, crossing a dangerous area, or visiting a dungeon, these commands help get your character where they need to be.


## 4. Farming

Now that your character knows how to get around, it's time to put them to work!

The `farm` command starts a farming session. You can use it on the map you're currently visiting, or tell it to travel to another map first. You can also decide how long to farm, which monsters to target, and when to stop.

### Starting a farming session

The simplest form is:

    farm

On its own, `farm` fights on the map you're currently on, using the map's whole monster area. It keeps going until a stop rule or the Stop key ends the run.

You can also add options to customize the session.

### Choosing where to farm

Use `map=` to send your character to a particular map before farming.

    farm map="Wolf Prairie"

You can identify the map by its name or number, just like with the `travel` command.

### Setting a farming limit

You can decide when a farming session should finish by setting a time limit or a kill target.

    minutes=<N>    stop farming after N minutes
    kills=<N>      stop farming after N kills

For example:

    farm map="Wolf Prairie" minutes=30
    farm kills=200

The first example farms Wolf Prairie for 30 minutes. The second stops after 200 kills.

### Choosing a patrol pattern

By default, the bot wanders around the map at random. You can change this with `patrol=`.

    patrol=<random|full|quick|short>

Here is what each option does:

- `random` wanders around randomly. This is the default.
- `full` follows a patrol loop that passes close to every spot on the map.
- `quick` follows a shorter loop that passes close to most spots.
- `short` takes the shortest lap that keeps nearly the whole map within 40 walking steps. This is especially useful in mazes, such as turkey cave.

When using a patrol loop, monsters more than 40 walking steps away are left alone until the next lap brings your character close enough.

For example:

    farm map="Wolf Prairie" patrol=full

### Limiting the farming area

Sometimes you only want to farm in a particular part of a map. Use `area=` to define a rectangular area where the bot is allowed to fight.

    area=<x1>,<y1>,<x2>,<y2>

The four numbers describe the rectangle using two coordinate points: `x1,y1` and `x2,y2`. Monsters outside this rectangle are ignored.

For example:

    farm map="central plains" area=180,150,240,210

This sends your character to central plains and limits farming to the rectangle defined by those coordinates.

### Controlling which monsters to fight

Sometimes you don't want your character fighting everything in sight. You can use `only=` and `skip=` to choose which monsters to target.

    only=<names>    only fight monsters whose names contain one of these
    skip=<names>    never fight these monsters

You can provide several names by separating them with `|`. Put the names inside quotation marks.

For example:

    farm kills=200 only="wolf|fox"

This only targets monsters whose names contain `wolf` or `fox`.

You can also use `skip=` to avoid specific monsters:

    farm skip="Boar King"

### Avoiding elite zones

Use `elites=` to decide whether your character should enter elite zones.

    elites=<fight|avoid>

- `fight` allows your character to enter elite zones.
- `avoid` keeps your character out of them.

For example:

    farm map="Orcus Tribe" elites=avoid

### Stopping when a condition is met

You can use `until=` to stop farming as soon as a condition becomes true.

    farm map=5301 until=bag("Large Red Potion") < 20

This example stops the farming session when your bag has fewer than 20 Large Red Potions.

**Important:** `until=` takes everything after it as its condition, so it must always be the last option on the line.

### Combining farming options

You can combine the options in any order, as long as `until=` comes last.

For example:

    farm map="Wolf Prairie" minutes=30 patrol=full
    farm kills=200 only="wolf|fox" elites=avoid
    farm map=5301 until=bag("Large Red Potion") < 20

Each example combines different options to control the farming session.

When a `farm` line finishes, the script moves on to the next line. If you don't set `minutes=`, `kills=`, or `until=`, farming continues until the entire run is stopped.


## 5. Stopping well

A good script needs to know when to stop and what to do afterward. Maybe you've run out of potions, reached your kill target, or simply spent enough time farming for the day.

Uncle Farmer gives you several ways to control how a run ends.

### Setting automatic stop rules

Use `stop_when` to tell the bot when it should end the run.

    stop_when <condition> : <message>

A stop rule keeps watching for its condition, even in the middle of a fight. Once the condition becomes true, the run ends.

It's best to put your stop rules near the top of the script so they can watch the entire run.

For example:

    stop_when bag("Large Red Potion") < 10 : out of red potions
    stop_when clock == "23:00" : bed time
    stop_when minutes >= 120 : two hours are enough

The message after `:` is written in the log and spoken aloud, so you'll know why the run stopped.

### Stopping immediately

Sometimes you don't need to wait for a condition. You can use `stop` to end the run right away.

    stop <message>

For example:

    stop reached the end of the task

The message is optional. This command ends the run immediately and moves on to the run's ending behavior.

### Choosing where the run ends

Use `end_at` to decide where your character should go when the run finishes.

    end_at <where>

This applies regardless of what ends the run: a stop rule, the end of the script, the drop time, a full bag, the last death, or broken gear.

Put this command near the top of your script.

Here are the available destinations:

    end_at start                         return to where the run started (the default)
    end_at 1041 at 200,205               go to a map and a specific spot on it
    end_at hearthstone                   return home using the hearthstone
    end_at safe                          go to the nearest map where no monsters spawn
    end_at here                          stay where you are

There is one special detail about `start`: if the run began on a map where monsters spawn, the bot ends on the nearest map without monsters instead. If returning to the starting location fails for any reason, it also ends there.

### Saving some drop time for later

You can use `keep_drop` to finish the run while some of the day's drop time is still available.

    keep_drop <minutes>

For example:

    keep_drop 60

This tells the bot to end the run while an hour of the day's drop time remains. The bot may continue running for a few minutes after leaving the monsters.

This setting applies to the current run only and takes priority over your character's own **Drop time to save** setting under **Bag and supplies → Full bag**.

You can also configure the same setting in a plan's **When to stop** page.

### Running commands when the run ends

Use `on_stop` when you want the bot to perform additional actions at the end of a run.

    on_stop
      <commands>
    end

The commands inside this block run whenever the run ends, whether because of a stop rule, the `stop` command, or the end of the script.

For example:

    on_stop
      hearthstone
      say finished with {kills} kills
    end

This sends your character home and writes the number of kills to the log.

**One important exception:** `on_stop` does not run when you press the Stop key yourself. In that case, the bot simply releases all keys at once.

With these commands, you can decide not only when a script finishes, but also what happens when it does.


## 6. What the bot can read

Your script doesn't have to rely on fixed instructions. It can also check what's happening in the game and make decisions based on that information.

Uncle Farmer provides several built-in names and functions that you can use in conditions and in the `say` command.

### Checking your character's status

These names let your script check your character's health, mana, and level.

| Name | What it tells you |
|---|---|
| `hp` | Your current HP |
| `maxhp` | Your maximum HP |
| `hp_pct` | Your HP as a percentage |
| `mp` | Your current MP |
| `maxmp` | Your maximum MP |
| `mp_pct` | Your MP as a percentage |
| `level` | Your character's level |

**A note about MP and level:** These values come from the server's answer to the own-HP request, which is sent without a key from agent 39, and from your character sheet. Until the bot has received them, their values are `-1`.

### Checking your location

You can also check where your character is currently standing.

| Name | What it tells you |
|---|---|
| `map` | The map's number |
| `map_name` | The map's name |
| `x` | Your current X coordinate |
| `y` | Your current Y coordinate |

### Tracking your farming progress

These values help you keep track of what your character has accomplished during the current run.

| Name | What it tells you |
|---|---|
| `kills` | The number of monsters killed during this run |
| `minutes` | How many minutes have passed since the run started |
| `clock` | The current time of day, such as `"21:45"` |
| `monsters` | The number of monsters currently around you |
| `arnebia_gained` | Arnebia gained during this run |
| `shards_gained` | Shards gained during this run |
| `xp_gained` | Experience gained during this run |
| `levels_gained` | Levels gained during this run |
| `contribution_gained` | Contribution gained during this run |

For `shards_gained`, every shard picked up counts, even if it was later thrown away.

### Checking items in your bag

The `bag()` function tells you how many of a particular item you currently have.

    bag("<item name>")

For example:

    stop_when bag("Large Red Potion") < 10 : out of red potions

This checks whether you have fewer than 10 Large Red Potions.

### Using number functions

Uncle Farmer also provides a few useful mathematical functions.

| Function | What it does |
|---|---|
| `random(a, b)` | Returns a random whole number between `a` and `b` |
| `min(a, b)` | Returns the smaller of two values |
| `max(a, b)` | Returns the larger of two values |
| `abs(x)` | Returns the absolute value of a number |
| `round(x)` | Rounds a number |
| `int(x)` | Converts a value to an integer |

For example, `random(1, 10)` gives you a random whole number from 1 to 10.

### Comparing values

Conditions use comparison operators to check whether one value is smaller, larger, equal to, or different from another.

Here are the available operators:

- `<` means less than.
- `<=` means less than or equal to.
- `>` means greater than.
- `>=` means greater than or equal to.
- `==` means equal to.
- `!=` means not equal to.

You can also combine conditions using `and`, `or`, and `not`.

For example:

    stop_when hp_pct < 30 and monsters > 3 : too dangerous here

This stops the run when your HP is below 30 percent and there are more than three monsters around you.

These built-in names and functions give your scripts a way to respond to what's happening instead of simply following the same instructions every time.


## 7. Decisions and loops

So far, your scripts have followed commands in order. But what if you want the bot to make a choice? Or repeat a task several times without writing the same commands over and over?

That's where decisions and loops come in.

### Making decisions with `if`, `elif`, and `else`

The `if` command lets your script check a condition and choose what to do.

You can use `elif` to check another condition if the first one isn't true. If none of the conditions match, `else` provides a final alternative.

For example:

    if bag("Large Red Potion") < 50
      buy 200 "Large Red Potion"
    elif bag("Large Red Potion") < 100
      say potions are getting low: {bag("Large Red Potion")} left
    else
      say plenty of potions
    end

Here's how this script makes its decision:

- If you have fewer than 50 Large Red Potions, it buys 200.
- Otherwise, if you have fewer than 100, it reports how many are left.
- If neither condition is true, it reports that you have plenty.

Every `if` block needs a matching `end`.

### Repeating tasks with `repeat`

The `repeat` command runs a group of commands more than once.

You can give it a number to specify how many times to repeat the commands.

    repeat 3
      farm minutes=10
    end

This farms for 10 minutes, three times.

You can also use `repeat` without a number. In that case, it keeps repeating until something stops the run.

For example:

    repeat
      farm map="Wolf Prairie" minutes=20
      farm map="Orcus Tribe" minutes=20
    end

This sends your character to Wolf Prairie and Orcus Tribe in turn, spending 20 minutes farming on each map. Once both sessions finish, the script starts the cycle again.

### Repeating while a condition is true

The `while` command repeats a group of commands as long as a condition remains true.

    while kills < 500
      farm minutes=10
      say {kills} kills so far
    end

This keeps farming in 10-minute sessions until the kill count reaches 500 or more.

Unlike `repeat`, which can run a fixed number of times or continue indefinitely, `while` checks a condition to decide whether another repetition should happen.

### Leaving a loop with `break`

Sometimes you want to leave a loop early, even if it could keep running.

Use `break` to exit the loop you're currently inside. The script then continues with the command immediately after that loop's `end`.

For example:

    repeat
      farm minutes=15
      if clock >= "22:00"
        break
      end
    end
    hearthstone

This repeats 15-minute farming sessions, but leaves the loop once the time reaches 22:00. After that, the script continues to `hearthstone`.

With decisions and loops, your scripts can respond to changing conditions, repeat useful tasks, and stop at the right moment.


## 8. Your own values

So far, we've used information that Uncle Farmer already provides, such as `kills`, `hp_pct`, and `level`.

But what if you want your script to keep track of something of its own?

That's what `set` is for. It lets you store a value under a name you choose, then use that value elsewhere in your script.

### Creating your own values with `set`

The basic form is:

    set <name> = <value>

For example:

    set rounds = 0

This creates a value named `rounds` and gives it an initial value of `0`.

You can change that value later:

    set rounds = rounds + 1

Each time this command runs, the value of `rounds` increases by one.

### Displaying values with `say`

The `say` command writes a message to the log. You can include your own values, built-in values, and calculations inside `{ }`. Uncle Farmer works them out before displaying the message.

For example:

    say round {rounds} done, {kills} kills, HP {hp_pct}%

### Putting it all together

Here's a small script that counts how many farming rounds have been completed:

    set rounds = 0
    repeat
      farm minutes=15
      set rounds = rounds + 1
      say round {rounds} done, {kills} kills, HP {hp_pct}%
    end

Each time a farming session finishes, the script increases `rounds` by one and reports the progress.

Your own values can be used anywhere the bot's built-in names can. This makes it easier to keep track of progress and build scripts that remember information as they run.


## 9. Blocks you can reuse

As your scripts get longer, you may find yourself writing the same group of commands more than once.

For example, perhaps you need to visit a shop and refill your potions whenever your supplies run low. Instead of writing those commands every time, you can put them together in a reusable block.

That's what `sub` and `call` are for.

### Creating a reusable block with `sub`

Use `sub` to give a group of commands a name.

    sub <name>
      <commands>
    end

For example:

    sub refill
      travel "central plains"
      buy 200 "Large Red Potion"
      buy 200 "Large Blue Potion"
    end

This creates a reusable block named `refill`. It contains the commands for traveling to central plains and buying potions.

Defining a block doesn't run its commands immediately. It simply gives that group of commands a name.

### Running a reusable block with `call`

Whenever you want to run the commands inside a block, use `call` followed by its name.

    call <name>

For example, `call refill` runs the commands inside the `refill` block.

### Putting it all together

Here's an example that checks your potion supply and refills it when necessary:

    sub refill
      travel "central plains"
      buy 200 "Large Red Potion"
      buy 200 "Large Blue Potion"
    end

    repeat
      if bag("Large Red Potion") < 30
        call refill
      end
      farm map="Wolf Prairie" minutes=30
    end

The script defines the `refill` block first. During the farming loop, it checks whether you have fewer than 30 Large Red Potions. If you do, it calls `refill` before continuing to farm.

This keeps your script shorter and makes it easier to update repeated tasks. If you ever want to change how the refill works, you only need to edit the block in one place.


## 10. Towns, shops and the storehouse

Farming isn't the only thing your character can do. Uncle Farmer can also visit NPCs, buy and sell items, manage your supplies, and use several in-game tools.

Let's look at what each command can do.

### Visiting and talking to NPCs

Uncle Farmer has two commands for interacting with NPCs:

    visit <kind or NPC name>     go to the nearest NPC of a kind and open its menu
    talk <NPC name>              walk up to an NPC and open its menu
    choose <text>                pick the menu entry that contains this text

The `visit` command looks for the nearest NPC of a particular kind and opens its menu. The `talk` command lets you approach an NPC by name.

Once a menu is open, use `choose` to select an entry containing the text you provide.

For example:

    visit storehouse
    choose "item storage"

You can use `choose` to interact with menu entries that aren't handled by a dedicated command.

**Important:** If the requested menu entry isn't there, `choose` stops the run. This prevents your script from blindly selecting something else or continuing when the expected option is missing.

### Buying, selling and managing storage

These commands handle common shopping and storehouse tasks:

    buy <count> <item>           buy from the nearest shop that sells it
    sell <item> [count]          sell to the NPC that buys it (all of them if no count)
    withdraw <count> <item>      take items out of the storehouse
    deposit <item> [count]       put items into the storehouse (all of them if no count)
    restock                      top up your supplies now, as set in Bag and supplies

For `sell` and `deposit`, leaving out the count means the bot handles all available items.

The `buy`, `sell`, `withdraw`, and `deposit` commands take care of finding the right NPC, selecting the correct menu entries, and entering the quantity for you.

### NPC types recognized by `visit`

You don't always have to provide an NPC's exact name. The `visit` command recognizes these kinds:

- `storehouse`
- `potions`
- `grocer`
- `bank`
- `blacksmith`
- `forger`
- `gem_craftsman`
- `artificer`
- `shard_market`
- `fish_buyer`
- `herb_buyer`
- `ore_buyer`

For example:

    visit potions

This visits the nearest NPC of the `potions` kind and opens its menu.

### Using the Gem Maker and Equipment Enhancer

If you've configured these tools in Uncle Farmer, you can run them directly from a script.

    gem_maker          run the Gem Maker as set up in Tools
    gem_maker check    only look: walk there, read the menus and prices, change nothing
    enhance            run the Equipment Enhancer as set up in Tools
    enhance check      only look

The `check` options let you inspect what the bot would do without actually running the tool's actions.

### Running daily chores

The `chores` command runs the daily chores configured under **Tools → Daily chores**.

    chores                         run the configured daily chores
    chores check                   only look
    chores only=bank,donation      run just those chores

Each configured chore is performed once per game day.

You can use `only=` to choose which chores to run. The available names are:

- `bank`
- `bounty`
- `pet_rebirth`
- `donation`
- `construction`
- `feed`
- `secret_room`

For example:

    chores only=bank,donation

This runs only the bank and donation chores.

### Losing experience

The `lose_xp` command dies to guards on purpose, as set under **Tools → XP loser**, until the next level needs at least the experience you set (or until it has lost as much as you set).

    lose_xp          die to guards until the goal is met
    lose_xp check    only read the experience and look for guards; nothing changes

It switches the PK mode to all mode while it runs and puts it back at the end. No potions, heals or fighting back while it waits to die. It stops at the goal, after the most deaths you allow, or when dying no longer costs experience.

### Gathering and selling collections

The `gather` command handles fishing, mining, or herb collecting according to your settings under **Tools → Gathering**.

    gather          gather using the configured settings
    gather check    only look at the planned gathering actions

Gathering works in the gang's area once per game day, then outside that area. The character fights back when needed and sells the collection afterward.

The `gather check` option only looks at the skill, the gang area's entrance, and the place the bot would use.

If you want to sell the gathered items separately, use:

    sell_collection              sell fish, ore and herbs
    sell_collection fish         sell only one type: fish, ore or herb

The available types are `fish`, `ore`, and `herb`.

### Managing shards and your bag

Uncle Farmer also provides commands for handling shards and following your bag manager's settings.

**Selling shards**

    sell_shards

This sells the shards that your bag manager says to sell, using the nearest Shard Market. If the current city has a Shard Market, it uses that one.

This is the same action as **Sell shards now** in the game's menu under the Games list.

**Cleaning your bag**

    clean_bag

This throws away the items on your bag manager's throw-away list, while keeping anything protected by its rules. It only handles the items on that list and nothing else.

This is the same as **Clean the bag now** in the game's menu.

**Updating shard prices**

    update_shard_prices

This reads the prices from the nearest Shard Market and updates `data/shards.json`.

Only prices that the market menu both displays and sends are kept. Other prices remain unchanged.

This is the same as **Update shard prices** in the game's menu.

**Storing items**

    store_items

This puts items from your bag into the storehouse according to your bag manager's Store list. It respects the items each rule says to keep and does not store anything else.

This is the same as **Store items now** in the game's menu.

### Entering a dungeon

The `dungeon` command runs the cave configured under **Tools → Dungeons**.

    dungeon                       run the configured cave
    dungeon Spider cave           run Spider cave instead of the configured cave
    dungeon check                 only look at what is short and which cave it would enter

A character enters one cave per game day. The bot checks supplies first, then spends all 15 minutes inside.

You can use a different cave name after `dungeon` to choose that cave instead of the one configured in the window.

### Exploring NPCs and maps with `survey`

Sometimes you need to know what NPCs are available, where they stand, or what their menus contain. The `survey` command lets Uncle Farmer explore maps and collect that information directly from the game.

Here are the available forms:

    survey cities                the towns and villages only
    survey all                   every map the game's data puts NPCs, a town, a dungeon entrance or a
                                 transport on - not the plain farming fields - looking only round them
    survey everything            every map you can walk out of, farming fields too (it can take days)
    survey <map>                 one map
    survey here                  the map you are on, even one you can't walk to (your gang's base, a dungeon)

**What does a survey collect?**

A survey walks each map so every part of it comes into view. It records:

- Every NPC, including the game's own description of it.
- Every kind of monster, including its level.
- Each NPC's menu and the information available through it.

When reading menus, the bot only presses entries that show more information. It never selects an entry that buys, sells, takes, teleports, enters, or confirms.

Some NPCs or objects respond with a spoken line instead of opening a menu. For example, they might say "Requirements not met". The bot saves that line too.

**Where is the survey data saved?**

Each map is saved to the `survey` folder as soon as the survey finishes there. This means you can stop and start the survey again later, and it will pick up where it left off.

The bot travels from one map to the nearest map.

**How does the bot travel during a survey?**

The bot rides the Swift fusion beast for the entire journey, just like the walking assistant. It never stops to fight. It outruns anything that attacks it, while potions keep its HP up.

If your character dies, the bot sends them back to the map they were on.

A survey can cover a lot of ground, so make sure you use a character strong enough to handle the maps it visits.

One more detail: the day's farming stop, which happens before the drop-time reset, does not end a survey because the bot isn't farming during it.

With these commands, your scripts can do much more than fight monsters. They can handle everyday tasks, manage supplies, interact with NPCs, and even gather information about the game world.


## 11. Keys

Most of the time, Uncle Farmer handles movement, farming, potions, and menus for you. You won't need to press keys manually.

However, there may be times when you want your script to press a particular key, hold it down, or wait before continuing.

### Pressing and holding keys

Here are the available commands:

    key <key>                 press a key once
    key <key> <milliseconds>  press and hold it that long
    hold <key> <seconds>      hold a key down
    wait <seconds>            do nothing for a while
    heal                      drink an HP potion now

The `key` command normally presses a key once. You can also give it a duration in milliseconds to hold the key for that long.

The `hold` command uses seconds instead.

The `wait` command pauses the script for the number of seconds you specify. It doesn't perform any action during that time.

The `heal` command tells the bot to drink an HP potion immediately.

### Available key names

You can use the following key names:

- Letters and digits.
- `.`, `,`, `;`, `/`, and `space`.
- `enter`, `esc`, and `tab`.
- `f1` through `f12`.
- `up`, `down`, `left`, and `right`.

You can also combine keys, such as:

    key lctrl+alt+down

This presses the left Ctrl and Alt keys together with the Down arrow.

Most scripts won't need these commands because Uncle Farmer already handles farming, potions, travel, and menus automatically. Use manual key commands when you need to control a key directly.


## 12. Complete examples

You've now learned the main commands and how to combine them. Let's put them to work!

The following examples cover common scripting tasks, from farming across multiple maps to managing supplies and tracking progress.

You can copy any of these examples into the script editor and try them out.

### Farming on two maps with stop rules

This script alternates between two farming maps. It also stops at 11 PM or when your red potions run low.

    # Wolves and orcs, until 11 at night or the potions run low.
    stop_when bag("Large Red Potion") < 15 : out of red potions
    stop_when clock == "23:00" : bed time

    on_stop
      hearthstone
    end

    repeat
      farm map="Wolf Prairie" minutes=30 patrol=full
      farm map="Orcus Tribe" minutes=30 elites=avoid
    end

The script starts by setting two stop rules. If either condition becomes true, the run ends.

The `on_stop` block sends your character home when the run ends. Otherwise, the `repeat` loop keeps alternating between Wolf Prairie and Orcus Tribe.

### Farming, refilling, and returning

Running out of potions in the middle of a farming session can interrupt your plans. This script checks your supply and refills when needed.

    sub refill
      buy 200 "Large Red Potion"
      buy 100 "Large Blue Potion"
    end

    stop_when clock == "22:30" : evening is over

    repeat
      if bag("Large Red Potion") < 40
        call refill
      end
      farm map=5301 until=bag("Large Red Potion") < 40
    end

The `refill` block handles buying potions. The loop checks your red potion supply before each farming session and calls the block when fewer than 40 remain.

The farming session also ends when the red potion count drops below 40. The loop then checks again and refills if necessary.

The stop rule makes sure the run ends when the clock reaches 22:30.

### Reaching a kill target and tracking progress

If you have a specific number of kills in mind, you can use a variable and a `while` loop to track your progress.

    set goal = 1000
    while kills < goal
      farm map="Wolf Prairie" minutes=10
      say {kills} of {goal} kills, {arnebia_gained} arnebia so far
    end
    say goal reached
    hearthstone

The script keeps farming in 10-minute sessions until the kill count reaches 1,000.

After each session, it reports your current kill count and the amount of Arnebia gained. Once the target is reached, it announces that the goal has been reached and sends your character home.

### Targeting specific monsters in one area

You don't always need to farm an entire map. You can limit your farming area and choose exactly which monsters to target.

    farm map="central plains" area=180,150,240,210 only="boar" skip="Boar King" minutes=45

This sends your character to central plains and limits farming to the rectangle between the specified coordinates.

It only targets monsters whose names contain `boar`, while skipping `Boar King`. The session lasts for 45 minutes.

### Earning contribution before stopping

You can also set a target for contribution gained during a run.

    stop_when contribution_gained >= 5000 : 5000 contribution earned
    farm map="Orcus Tribe"

This starts farming in Orcus Tribe and keeps going until the run has gained at least 5,000 contribution.

Once the target is reached, the stop rule ends the run and displays the message in the log.

These examples are starting points. Feel free to change the maps, targets, times, and conditions to suit your own plans.


## 13. When something goes wrong

Even a small mistake can prevent a script from running correctly. Don't worry, though. Most scripting problems are easy to find once you know where to look.

Here are a few things to check when something doesn't work as expected.

### Check your script with F5

Press **F5** regularly while writing your script. This checks whether Uncle Farmer can understand the commands.

If something is wrong, the bot reports the line and describes the problem.

For example:

> line 4: farm: unknown option "minuts"

The cursor also jumps to the line with the problem, making it easier to find and fix the mistake.

In this example, `minuts` should be `minutes`.

### Check that every block has an `end`

Commands such as `repeat`, `if`, `while`, `sub`, and `on_stop` open blocks.

Every block needs its own matching `end`. A missing `end` is one of the most common scripting mistakes.

For example:

    repeat
      farm minutes=30
      say farming session finished
    end

Make sure you don't accidentally leave out the final `end` when writing longer scripts.

### Put names with spaces in quotes

Map names, item names, and other names containing spaces must be wrapped in quotation marks.

Correct:

    travel "Wolf Prairie"

Incorrect:

    travel Wolf Prairie

Without quotation marks, the bot may not understand where the name begins or ends.

### Check the Log tab

The **Log** tab shows what the bot did, line by line. If a script behaves differently from what you expected, the log can help you see what happened.

The day's log is also saved in the `logs` folder, so you can check it later.

### Test your script safely

If you're trying out a new script or testing an unfamiliar command, it's a good idea to limit how long it can run.

Add this stop rule near the top:

    stop_when minutes >= 5 : test over

This ends the run after five minutes, giving you a chance to check whether everything works as expected.

### Turning a plan into a script

You don't always have to start from an empty editor.

If you already have a plan you like, open it in the plan editor and use **Save as script**.

Uncle Farmer converts the plan into script lines that you can then edit and customize.

With a little testing and the help of the Log tab, you'll be able to find and fix most scripting problems.


## Quick reference

Use this section when you need a quick reminder of a command or its syntax.

### Travel and movement

    travel <map> [at x,y]           walk to a map, optionally to a specific cell
    walk <x> <y>                    walk to a cell on the current map
    go <map> [at <x>,<y>]           use the walking assistant to reach a map
    go <map> at <x>,<y> to <npc>    reach a map and walk up to an NPC
    go dungeon <name>               walk up to a dungeon's entrance NPC
    go dungeon <name> talk          walk to the entrance and open its menu

### Farming

    farm [map=<map>] [minutes=<N>] [kills=<N>] [patrol=<kind>] [area=<x1>,<y1>,<x2>,<y2>]
         [only=<names>] [skip=<names>] [elites=<fight|avoid>] [until=<condition>]

### NPCs, shops and storage

    visit <kind>
    talk <npc>
    choose <text>
    buy <n> <item>
    sell <item> [n]
    withdraw <n> <item>
    deposit <item> [n]
    restock

### Tools and daily activities

    gem_maker [check]
    enhance [check]
    chores [check] [only=...]
    gather [check]
    lose_xp [check]
    sell_collection [fish|ore|herb|all]
    sell_shards
    clean_bag
    update_shard_prices
    store_items
    dungeon [check] [<cave>]

### Following players

    follow <player>
    come <player> [<map> [at x,y]]

### Keys and healing

    key <key> [ms]
    hold <key> <s>
    wait <s>
    heal
    hearthstone

### Messages and values

    say <text>
    set <name> = <value>

### Stopping and ending a run

    stop_when <condition> [: message]
    stop [message]
    on_stop ... end
    keep_drop <minutes>

### Decisions and loops

    repeat [N] ... end
    while <condition> ... end
    break
    if ... elif ... else ... end

### Reusable blocks

    sub <name> ... end
    call <name>

