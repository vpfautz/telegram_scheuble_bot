import telepot
from telepot.loop import MessageLoop
import time
from pprint import pprint
import sys
import sqlite3


"""
$ python scheuble_bot.py <token>

Counts messages from users and can display who sent how many.

top - Returns the top message senders in this channel
mystats - Returns your stats in this channel
reset - Resets stats for this channel (Admin only!)
"""


ANSWER_TIMEOUT = 10

def init_db():
	conn = sqlite3.connect('stats.db')
	c = conn.cursor()

	# Create table
	c.execute('CREATE TABLE IF NOT EXISTS counts (chat_id int, sender_id int, username text, count int)')
	c.execute('CREATE TABLE IF NOT EXISTS log (chat_id int, sender_id int, username text, date int, typ text)')

def inc_count(chat_id, sender_id, username, date, typ):
	conn = sqlite3.connect('stats.db')
	c = conn.cursor()

	c.execute("INSERT INTO log VALUES (?, ?, ?, ?, ?)", (chat_id, sender_id, username, date, typ))
	c.execute('SELECT count FROM counts where chat_id=? and sender_id=?', (chat_id, sender_id))
	r = c.fetchone()

	if not r:
		c.execute("INSERT INTO counts VALUES (?, ?, ?, ?)", (chat_id, sender_id, username, 1))
		conn.commit()
		return

	count = r[0] + 1

	c.execute("UPDATE counts set count=? where chat_id=? and sender_id=?", (count, chat_id, sender_id))
	conn.commit()

def get_count(chat_id, sender_id):
	conn = sqlite3.connect('stats.db')
	c = conn.cursor()

	c.execute('SELECT count FROM counts where chat_id=? and sender_id=?', (chat_id, sender_id))
	r = c.fetchone()

	if not r:
		return 0
	else:
		return r[0]

def get_type_count(chat_id, sender_id):
	conn = sqlite3.connect('stats.db')
	c = conn.cursor()

	r = c.execute('select typ, count(*) as count from log where chat_id=? and sender_id=? group by typ order by count desc', (chat_id, sender_id))
	return r.fetchall()

def get_avg(chat_id, sender_id):
	conn = sqlite3.connect('stats.db')
	c = conn.cursor()

	since = int(time.time()) - 24*3600
	r = c.execute('select count(*) from log where chat_id=? and sender_id=? and date>=?', (chat_id, sender_id, since))
	avg1 = r.fetchone()[0]

	since = int(time.time()) - 24*3600 * 7
	r = c.execute('select count(*) from log where chat_id=? and sender_id=? and date>=?', (chat_id, sender_id, since))
	avg7 = r.fetchone()[0]

	return (avg1, avg7)

def get_top(chat_id):
	conn = sqlite3.connect('stats.db')
	c = conn.cursor()

	r = c.execute('SELECT username, count FROM counts where chat_id=? order by count desc', (chat_id,))
	return r.fetchall()

def reset_count(chat_id):
	conn = sqlite3.connect('stats.db')
	c = conn.cursor()

	c.execute('DELETE FROM counts where chat_id=?', (chat_id,))
	c.execute('DELETE FROM log where chat_id=?', (chat_id,))
	conn.commit()


MSG_TYPES = [
	("edit_date", "EDIT"),
	("text", "TEXT"),
	("location", "LOCATION"),
	("video", "VIDEO"),
	("voice", "VOICE"),
	("photo", "PHOTO"),
	("document", "DOCUMENT"),
	("sticker", "STICKER"),
]

IGNORE_TYPES = [
	"migrate_from_chat_id",
	"pinned_message",
	"left_chat_member"
]

def get_type(msg):
	typ = None
	for keyword, t in MSG_TYPES:
		if keyword in msg:
			typ = t
			break

	if typ is None:
		print "unknown typ"
		pprint(msg)

	return typ

def handle(msg):
	# print ""
	# print "#"*40
	# pprint(msg)

	bot_name = bot.getMe()["username"]

	chat_id   = msg["chat"]["id"]
	sender_id = msg["from"]["id"]
	username  = msg["from"]["first_name"]
	date = msg["edit_date"] if "edit_date" in msg else msg["date"]

	if "new_chat_member" in msg:
		new_name = msg["new_chat_member"]["first_name"]
		bot.sendMessage(chat_id, u"Hello %s \U0001f60a" % new_name)
		return

	# ignore status messages
	for t in IGNORE_TYPES:
		if t in msg:
			return

	if not "text" in msg:
		typ = get_type(msg)
		inc_count(chat_id, sender_id, username, date, typ)
		return

	text = msg["text"]

	if text == "/mystats" or text == "/mystats@%s" % bot_name:
		if time.time() - date > ANSWER_TIMEOUT:
			return
		count = get_count(chat_id, sender_id)
		out = "%s, you sent %s messages in this channel.\n" % (username, count)
		stats = get_type_count(chat_id, sender_id)
		out += "\n".join("%s: %s (%.1f%%)" % (name, c, 100.*c/count) for name,c in stats)
		avg1, avg7 = get_avg(chat_id, sender_id)
		out += "\nday: %s, week: %s" % (avg1, avg7)

		# trend
		if avg1*7 > avg7:
			out += u" \u2197\ufe0f" # up
		elif avg1*7 < avg7:
			out += u" \u2198\ufe0f" # down

		bot.sendMessage(chat_id, out)
		return

	if text == "/top" or text == "/top@%s" % bot_name:
		if time.time() - date > ANSWER_TIMEOUT:
			return
		top = get_top(chat_id)
		total = sum(map(lambda x:x[1], top))
		out = ""
		for u,c in top:
			out += "%s: %s (%.1f%%)\n" % (u, c, 100.*c/total)
		bot.sendMessage(chat_id, out)
		return

	if text == "/reset" or text == "/reset@%s" % bot_name:
		if time.time() - date > ANSWER_TIMEOUT:
			return
		isadmin = False
		for admin in bot.getChatAdministrators(chat_id):
			if admin["user"]["id"] == sender_id:
				isadmin = True
				break

		if not isadmin:
			bot.sendMessage(chat_id, "%s, you're not an admin!" % username)
			return

		reset_count(chat_id)
		bot.sendMessage(chat_id, "%s, done." % username)
		return

	typ = get_type(msg)
	inc_count(chat_id, sender_id, username, date, typ)


if __name__ == '__main__':
	TOKEN = sys.argv[1]

	init_db()

	bot = telepot.Bot(TOKEN)
	MessageLoop(bot, handle).run_as_thread()

	print "Listening..."
	while True:
		time.sleep(10)
