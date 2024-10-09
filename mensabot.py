import discord
from discord import app_commands

import requests
import datetime
import re
import time

MY_GUILD = discord.Object(id=435769427481591818)

class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        # A CommandTree is a special type that holds all the application command
        # state required to make it work. This is a separate class because it
        # allows all the extra state to be opt-in.
        # Whenever you want to work with application commands, your tree is used
        # to store and work with them.
        # Note: When using commands.Bot instead of discord.Client, the bot will
        # maintain its own tree instead.
        self.tree = app_commands.CommandTree(self)

    # In this basic example, we just synchronize the app commands to one guild.
    # Instead of specifying a guild to every command, we copy over our global commands instead.
    # By doing so, we don't have to wait up to an hour until they are shown to the end-user.
    async def setup_hook(self):
        # This copies the global commands over to your guild.
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        #await self.tree.sync()

intents = discord.Intents.default()
client = MyClient(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')

@client.tree.command(name='sync', description='Owner only')
async def sync(interaction: discord.Interaction):
    if interaction.user.id == 240799236113956864:
        await client.tree.sync()
        await interaction.response.send_message('Command tree synced')
    else:
        await interaction.response.send_message('You must be the owner to use this command!')
    await interaction.response.defer()

# Enter server ID in guild_ids
@client.tree.command(name="mensa", description="Speiseplan der Mensa der Uni Tübingen oder Nürtingen")
@app_commands.describe(location="Standort",
                        period="Zeitraum")
@app_commands.choices(location=[
    app_commands.Choice(name="Morgenstelle", value="Morgenstelle"),
    app_commands.Choice(name="Wilhelmstraße", value="Wilhelmstraße"),
    app_commands.Choice(name="Prinz Karl", value="Prinz Karl"),
    app_commands.Choice(name="Nürtingen", value="Nürtingen"),
    ])
@app_commands.choices(period=[
    app_commands.Choice(name="Diese Woche", value="Diese Woche"),
    app_commands.Choice(name="Heute", value="Heute"),
    app_commands.Choice(name="Nächste Woche", value="Nächste Woche"),
    ])
async def mensa(interaction: discord.Interaction, location: str = "Morgenstelle", period: str = "Diese Woche"):
    
    embed = await build_mensa_embed(location, period)
    if not embed:
        reply = await interaction.response.send_message("Keine Daten vom Studierendenwerk bekommen {}".format(":persevere:"))
        return await reply.add_reaction("😵")
    await interaction.response.send_message(embed=embed, view=PersistentMensaView())

async def build_mensa_embed(location: str, period: str):
    def embed_list_lines(embed,
                        lines,
                        field_name,
                        max_characters=1024,
                        inline=False):
        zero_width_space = u'\u200b'
        value = "\n".join(lines)
        if len(value) > 1024:
            value = ""
            values = []
            for line in lines:
                if len(value) + len(line) > 1024:
                    values.append(value)
                    value = ""
                value += line + "\n"
            if value:
                values.append(value)
            embed.add_field(name=field_name,
                            value=values[0], inline=inline)
            for v in values[1:]:
                embed.add_field(name=zero_width_space,
                                value=v, inline=inline)
        else:
            embed.add_field(name=field_name, value=value, inline=inline)
        return embed

    def next_weekday(d, weekday):
        days_ahead = weekday - d.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        return d + datetime.timedelta(days_ahead)

    def get_data(id):
        # Get data
        url_mensa = "https://www.my-stuwe.de/wp-json/mealplans/v1/canteens/{}?lang=de".format(
            id)
        r = requests.get(url_mensa)
        r.encoding = 'utf-8-sig'
        data = r.json()
        return data

    def build_menu(data, caf=False):
        menu = []
        menu_cur_day = []
        for id in data:
            # If meal matches today
            if str(day.date()) in id["menuDate"]:
                # Collect meal for this day
                if caf:
                    menuLine = "Cafeteria"
                else:
                    menuLine = id["menuLine"]
                if "Dessert" not in menuLine and "Beilagen" not in menuLine and "Salat" not in menuLine:
                    price = id["studentPrice"]
                    # Append newline to last entry
                    if id["menu"]:
                        id["menu"][-1] = id["menu"][-1] + "\n"
                    for food in id["menu"]:
                        if caf:
                            if re.match("^Pommes frites$", food):
                                continue
                        food = "-{}".format(food)
                        menu.append(food)
                    if not menu:
                        continue
                    # menu is fully available, build string
                    menu_cur_day.append(
                        ["*{} - {}€*".format(menuLine, price)])
                    menu_cur_day.append(menu)
                    # Reset menu
                    menu = []
        return menu_cur_day

    # Get time stuff
    today = datetime.datetime.now()
    cal_week = today.strftime("%W")
    weekday = datetime.datetime.today().weekday()
    week_start = today - datetime.timedelta(days=weekday)
    week_end = today + datetime.timedelta(days=4 - weekday)
    heute_flag = False

    color = discord.Colour.magenta()
    mensa_id = "621"  # Tuebingen Morgenstelle
    caf_id = "724"
    emoji_map = {"[S]": "[ :pig2: ]",
                    "[R]": "[ :cow2: ]",
                    "[S/R]": "[ :pig2: / :cow2: ]",
                    "[F]": "[ :fish: ]",
                    "[G]": "[ :rooster: ]",
                    "[V]": "[ :seedling: ]",
                    "[L]": "[ :sheep: ]",
                    "[W]": "[ :deer: ]",
                    "[vegan]": "[ <:vegan:643514903029743618> ]",
                    "Tagesmenü -": ":spaghetti: Tagesmenü -",
                    "Tagesmenü 2 -": ":spaghetti: Tagesmenü 2 -",
                    "Tagesmenü vegetarisch -": ":seedling: Tagesmenü vegetarisch -",
                    "mensaVital": ":apple: mensaVital",
                    "Cafeteria": ":coffee: Cafeteria",
                    "Angebot des Tages": ":dollar: Angebot des Tages"}

    if period:
        if period == "Nächste Woche":
            cal_week = int(cal_week) + 1
            today = next_weekday(today, 0)
            weekday = 0
            week_start = today
            week_end = week_start + datetime.timedelta(days=4)
        elif period == "Heute":
            heute_flag = True

    if location:
        if location == "Wilhelmstraße":
            # Mensa wilhelmstrasse
            mensa_id = "611"
        elif location == "Nürtingen":
            # Nuertingen
            mensa_id = "665"
        elif location == "Morgenstelle":
            mensa_id = "621"  # Tuebingen Morgenstelle
        elif location == "Prinz Karl":
            mensa_id = "623"  # Tuebingen Morgenstelle


    data = get_data(mensa_id)
    if location and location == "Morgenstelle":
        data_caf = get_data(caf_id)
    else:
        data_caf = None

    # No data from Studierendenwerk
    if not data:
        return None

    # Needed later
    wochentage = ["Montag", "Dienstag", "Mittwoch",
                "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    needed_days = []

    # Show next week on weekends
    if weekday > 4:
        # could also use next_weekday() here
        today = next_weekday(today, 0)
        weekday = 0
        week_start = today
        week_end = week_start + datetime.timedelta(days=4)

    # Get Weekdays from today till friday
    if heute_flag:
        if weekday > 4:
            today = next_weekday(today, 0)
        needed_days.append(today)
    else:
        for day in range(weekday, 5):
            days_till_end_of_week = 4 - day
            needed_days.append(
                today + datetime.timedelta(days=days_till_end_of_week))

    needed_days.reverse()
    canteen = data[mensa_id]["canteen"]
    if heute_flag:
        title=f"{canteen}, am {today.strftime('%d.%m.')}"
        
    else:
        title = f"{canteen}, KW {cal_week} vom {week_start.strftime('%d.%m.')} bis {week_end.strftime('%d.%m.')}"
    embed = discord.Embed(title=f"{title} ({period})" , color=color)
    for day in needed_days:
        cur_weekday = day.weekday()
        # Go through all meals (6/day)
        menu_cur_day = build_menu(data[mensa_id]["menus"])
        if data_caf:
            # Collect data for cafeteria
            menu_cur_day_caf = build_menu(
                data_caf[caf_id]["menus"], caf=True)
            # Flatten list
            menu_cur_day_caf = [
                item for sublist in menu_cur_day_caf for item in sublist]
            # Append to menu
            menu_cur_day.append(menu_cur_day_caf)
        # Flatten list
        menu_cur_day = [
            item for sublist in menu_cur_day for item in sublist]
        if menu_cur_day == []:
            menu_cur_day = "Keine Daten vorhanden"
            embed.add_field(
                name="> **{}**".format(wochentage[cur_weekday]), value=menu_cur_day)
        else:
            # Do emoji mapping here
            for k, v in emoji_map.items():
                menu_cur_day = [w.replace(k, v) for w in menu_cur_day]
            # build embed here
            embed = embed_list_lines(
                embed, menu_cur_day, "> **{}**".format(wochentage[cur_weekday]), inline=True)
    embed.set_thumbnail(
        url='https://upload.wikimedia.org/wikipedia/commons/thumb/b/bf/Studentenwerk_T%C3%BCbingen-Hohenheim_logo.svg/220px-Studentenwerk_T%C3%BCbingen-Hohenheim_logo.svg.png')
    embed.set_footer(text='Bot by Fabi / N1tR0#0914')
    return embed

class PersistentMensaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update_embed(self, interaction: discord.Interaction, location=None, period=None):
        old_e = interaction.message.embeds[0]
        old_e_dict = old_e.to_dict()
        old_title = old_e_dict['title']

        if not period:
            period = re.findall(r"\(.*\)$", old_title)[0].replace("(", "").replace(")", "")
        if not location: 
            location = re.findall(r"Mensa .*,", old_title)[0].replace("Mensa ", "").replace(",", "")

        new_embed = await build_mensa_embed(location, period)
        await interaction.message.edit(embed=new_embed)
        await interaction.response.defer()
        time.sleep(0.5)

    @discord.ui.button(emoji="1️⃣", label="Morgenstelle", style=discord.ButtonStyle.grey, custom_id='persistent_view:ms')
    async def morgenstelle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_embed(interaction, location="Morgenstelle")

    @discord.ui.button(emoji="2️⃣", label="Wilhelmstraße", style=discord.ButtonStyle.grey, custom_id='persistent_view:sh')
    async def wilhelmstrasse(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_embed(interaction, location="Wilhelmstraße")

    @discord.ui.button(emoji="3️⃣", label="Prinz Karl", style=discord.ButtonStyle.grey, custom_id='persistent_view:pk')
    async def karl(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_embed(interaction, location="Prinz Karl")

    @discord.ui.button(emoji="🕐", label="Heute", style=discord.ButtonStyle.grey, custom_id='persistent_view:heute', row=2)
    async def today(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_embed(interaction, period="Heute")

    @discord.ui.button(emoji="🗓️", label="Diese Woche", style=discord.ButtonStyle.grey, custom_id='persistent_view:this_week', row=2)
    async def this_week(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_embed(interaction, period="Diese Woche")

    @discord.ui.button(emoji="🗓️", label="➡️ Nächste Woche", style=discord.ButtonStyle.grey, custom_id='persistent_view:next_week', row=2)
    async def next_week(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_embed(interaction, period="Nächste Woche")
        

client.run("")
client.add_view(PersistentMensaView())
