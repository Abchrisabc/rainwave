import time

from libs import db
from libs import log

from rainwave.playlist_objects.metadata import AssociatedMetadata
from rainwave.playlist_objects.metadata import make_searchable_string

class SongGroup(AssociatedMetadata):
	select_by_name_query = "SELECT group_id AS id, group_name AS name, group_name_searchable AS name_searchable, group_elec_block AS elec_block, group_cool_time AS cool_time FROM r4_groups WHERE group_name = %s"
	select_by_id_query = "SELECT group_id AS id, group_name AS name, group_name_searchable AS name_searchable, group_elec_block AS elec_block, group_cool_time AS cool_time FROM r4_groups WHERE group_id = %s"
	select_by_song_id_query = "SELECT r4_groups.group_id AS id, r4_groups.group_name AS name, r4_groups.group_name_searchable AS name_searchable, group_elec_block AS elec_block, group_cool_time AS cool_time, group_is_tag AS is_tag FROM r4_song_group JOIN r4_groups USING (group_id) WHERE song_id = %s"
	disassociate_song_id_query = "DELETE FROM r4_song_group WHERE song_id = %s AND group_id = %s"
	associate_song_id_query = "INSERT INTO r4_song_group (song_id, group_id, group_is_tag) VALUES (%s, %s, %s)"
	has_song_id_query = "SELECT COUNT(song_id) FROM r4_song_group WHERE song_id = %s AND group_id = %s"
	check_self_size_query = "SELECT COUNT(song_id) FROM r4_song_group JOIN r4_songs USING (song_id) WHERE group_id = %s AND song_verified = TRUE"
	delete_self_query = "DELETE FROM r4_groups WHERE group_id = %s"

	def _insert_into_db(self):
		self.id = db.c.get_next_id("r4_groups", "group_id")
		return db.c.update("INSERT INTO r4_groups (group_id, group_name, group_name_searchable) VALUES (%s, %s, %s)", (self.id, self.data['name'], make_searchable_string(self.data['name'])))

	def _update_db(self):
		return db.c.update("UPDATE r4_groups SET group_name = %s, group_name_searchable = %s WHERE group_id = %s", (self.data['name'], make_searchable_string(self.data['name']), self.id))

	def _start_cooldown_db(self, sid, cool_time):
		cool_end = int(cool_time + time.time())
		log.debug("cooldown", "Group ID %s Station ID %s cool_time period: %s" % (self.id, sid, cool_time))
		# Make sure to update both the if and else SQL statements if doing any updates
		if db.c.allows_join_on_update:
			db.c.update("UPDATE r4_song_sid SET song_cool = TRUE, song_cool_end = %s "
						"FROM r4_song_group "
						"WHERE r4_song_sid.song_id = r4_song_group.song_id AND r4_song_group.group_id = %s "
						"AND r4_song_sid.sid = %s AND r4_song_sid.song_exists = TRUE AND r4_song_sid.song_cool_end <= %s",
						(cool_end, self.id, sid, cool_end))
		else:
			song_ids = db.c.fetch_list(
				"SELECT song_id "
				"FROM r4_song_group JOIN r4_song_sid USING (song_id) "
				"WHERE r4_song_group.group_id = %s AND r4_song_sid.sid = %s AND r4_song_sid.song_exists = TRUE AND r4_song_sid.song_cool_end < %s",
				(self.id, sid, time.time() - cool_time))
			for song_id in song_ids:
				db.c.update("UPDATE r4_song_sid SET song_cool = TRUE, song_cool_end = %s WHERE song_id = %s AND sid = %s", (cool_end, song_id, sid))

	def _start_election_block_db(self, sid, num_elections):
		if db.c.allows_join_on_update:
			# refer to song.set_election_block for base SQL
			db.c.update("UPDATE r4_song_sid "
						"SET song_elec_blocked = TRUE, song_elec_blocked_by = %s, song_elec_blocked_num = %s "
						"FROM r4_song_group "
						"WHERE r4_song_sid.song_id = r4_song_group.song_id AND "
						"r4_song_group.group_id = %s AND r4_song_sid.sid = %s AND song_elec_blocked_num < %s",
						('group', num_elections, self.id, sid, num_elections))
		else:
			table = db.c.fetch_all("SELECT r4_song_group.song_id FROM r4_song_group JOIN r4_song_sid ON (r4_song_group.song_id = r4_song_sid.song_id AND r4_song_sid.sid = %s) WHERE group_id = %s", (self.id, sid))
			for row in table:
				song = Song()
				song.id = row['song_id']
				song.set_election_block(sid, 'group', num_elections)