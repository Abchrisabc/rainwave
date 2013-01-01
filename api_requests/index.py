import tornado.web
import tornado.escape
import time
import hashlib

from api.server import handle_url
from api.web import RequestHandler
from api_requests import info
from api import fieldtypes

from libs import config
from libs import cache
from libs import log
from libs import db
from libs import buildtools
from rainwave.user import User

translations = {
	"en_CA": {
		1: "Streaming Video Game Music Radio.  Vote for the song you want to hear!",
		2: "OverClocked Remix Radio.  Vote for your favourite remixes!",
		3: "Video game cover bands and remixes.  Vote for your favourite artists!",
		4: "Streaming original game chiptunes.  Vote for the songs you want to hear!",
		5: "Streaming game music and remixes.  Vote for the songs you want to hear!"
	),
	"de_DE": {
		1: "Streaming Video Game Music Radio.  Stimme f�r den Song ab den du h�ren willst!",
		2: "OverClocked Remix Radio.  Stimme f�r deine lieblings remixes ab!",
		3: "Video game cover bands and remixes.  Stimme f�r deine lieblings Interpreten ab!",
		4: "Streaming original game chiptunes.  Stimme f�r den Song ab den du h�ren willst!",
		5: "Streaming game music and remixes.  Stimme f�r den Song ab den du h�ren willst!"
	),
	"es_CL": {
		1: "Radio por Internet de M�sica de Videojuegos.  �Vota por las canciones que quieres escuchar!",
		2: "La Radio de OverClocked Remix.  �Vota por tus remixes favoritos!",
		3: "Covers y Remixes de M�sica de Videojuegos.  �Vota por tus artistas favoritos!",
		4: "Transmitiendo chiptunes originales de videojuegos.  �Vota por las canciones que quieres escuchar!"
		5: "Transmitiendo m�sica original y remixes de videojuegos.  �Vota por las canciones que quieres escuchar!"
	),
	"fi_FI":
		1: "Videopelimusiikkia soittava internet-radio.  ��nest� haluamaasi kappaletta!",
		2: "OverClocked Remix internet-radio.  ��nest� haluamaasi remixi�!",
		3: "Videopelimusiikkia soittavia coverb�ndej� ja pelimusiikkiremixej�.  ��nest� suosikkiesitt�j��si!",
		4: "Videopelien chiptune-tyylist� musiikkia soittava internet-radio.  ��nest� haluamiasi kappaleita!",
		5: "Videopelimusiikkia ja niiden remixej� soittava internet-radio.  ��nest� haluamiasi kappaleita!"
	),
	"nl_NL": {
		1: "Luister Video Game Muziek Radio. Stem op het nummer dat je wilt horen!",
		2: "OverClocked Remix Radip. Stem op jouw favoriete remixen!",
		3: "Video game cover bands en remixen. Stem op jouw favoriete artiesten!"
	),
	"pt_BR": {
		1: "R�dio Online de M�sicas de Video Game.  Vote nas m�sicas que quiser ouvir!",
		2: "R�dio OverClocked Remix.  Vote nos seus remixes favoritos!",
		3: "Bandas cover e remixes de Video Game.  Vote nos seus artistas favoritos!",
		4: "Chiptunes Originais de Videgame.  Vote nas m�sicas que quiser ouvir!",
		5: "M�sicas e Remixes de Videogame.  Vote nas m�sicas que quiser ouvir!"
	),
	"se_SE": {}
}

@handle_url("authtest")
class MainIndex(tornado.web.RequestHandler):
	def prepare(self):
		self.info = []
		self.sid = fieldtypes.integer(self.get_cookie("r4sid", "1"))
		if not self.sid:
			self.sid = 1
		
		if self.request.host == "game.rainwave.cc":
			self.sid = 1
		elif self.request.host == "ocr.rainwave.cc":
			self.sid = 2
		elif self.request.host == "covers.rainwave.cc" or self.request.host == "cover.rainwave.cc":
			self.sid = 3
		elif self.request.host == "chiptune.rainwave.cc":
			self.sid = 4
		elif self.request.host == "all.rainwave.cc":
			self.sid = 5
		
		self.set_cookie("r4sid", str(self.sid), expires_days=365, domain=".rainwave.cc")
	
		self.user = None
		if not fieldtypes.integer(self.get_cookie("phpbb3_38ie8_u", "")):
			self.user = User(1)
		else:
			user_id = int(self.get_cookie("phpbb3_38ie8_u"))
			if self.get_cookie("phpbb3_38ie8_sid"):
				session_id = db.c_old.fetch_var("SELECT session_id FROM phpbb_sessions WHERE session_id = %s AND session_user_id = %s", (self.get_cookie("phpbb3_38ie8_sid"), user_id))
				if session_id:
					db.c_old.update("UPDATE phpbb_sessions SET session_last_visit = %s, session_page = %s WHERE session_id = %s", (time.time(), "rainwave", session_id))
					self.user = User(user_id)
					self.user.authorize(self.sid, None, None, True)

			if not self.user and self.get_cookie("phpbb3_38ie8_k"):
				can_login = db.c_old.fetch_var("SELECT 1 FROM phpbb_sessions_keys WHERE key_id = %s AND user_id = %s", (hashlib.md5(self.get_cookie("phpbb3_38ie8_k")).hexdigest(), user_id))
				if can_login == 1:
					self.user = User(user_id)
					self.user.authorize(self.sid, None, None, True)

		if not self.user:
			self.user = User(1)
		self.user.ensure_api_key(self.request.remote_ip)
		self.user.data['sid'] = self.sid
		
		locale = self.get_cookie("r4lang", "en_CA")
		if locale in translations:
			if self.sid in translations[locale]:
				self.site_description = translations[locale][self.sid]
			else:
				self.site_description = translations['en_CA'][self.sid]
			self.locale = locale
		else:
			self.locale = "en_CA"
		
	# this is so that get_info can be called, makes us compatible with the custom web handler used elsewhere in RW
	def append(self, key, value):
		self.info.append({ key: value })

	def get(self):
		info.attach_info_to_request(self)
		self.set_header("Content-Type", "text/plain")
		self.render("index.html", request=self, info=tornado.escape.json_encode(self.info))
		
@handle_url("authtest_beta")
class BetaIndex(MainIndex):
	def get(self):
		if self.user.data['group_id'] not in (5, 4, 8, 12, 15, 14, 17):
			self.send_error(403)
		else:
			jsfiles = []
			jsroot, jssubdirs, jsfiles = os.walk(os.path.join(os.path.dirname(__file__), "../static/js"))
			buildtools.bake_css()
			
			info.attach_info_to_request(self)
			self.render("beta_index.html", request=self, info=tornado.escape.json_encode(self.info), jsfiles=jsfiles)