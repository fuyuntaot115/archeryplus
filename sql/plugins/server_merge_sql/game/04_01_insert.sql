ALTER TABLE XDS_guild_history_tb ADD NewHistoryUID BIGINT NOT NULL DEFAULT ( 0 );
GO

INSERT INTO account_tb SELECT a.* FROM XDS_account_tb a LEFT JOIN account_tb b ON a.AccountUID = b.AccountUID WHERE b.AccountUID IS NULL;
INSERT INTO money_account_tb SELECT a.* FROM XDS_money_account_tb a LEFT JOIN money_account_tb b ON a.AccountUID = b.AccountUID  AND a.MoneyIdx = b.MoneyIdx WHERE b.AccountUID IS NULL;
UPDATE b SET MoneyAmount += a.MoneyAmount FROM XDS_money_account_tb a INNER JOIN money_account_tb b ON a.AccountUID = b.AccountUID  AND a.MoneyIdx = b.MoneyIdx;
INSERT INTO money_dominion_storage_tb SELECT a.* FROM XDS_money_dominion_storage_tb a LEFT JOIN money_dominion_storage_tb b ON a.DominionTID = b.DominionTID AND a.MoneyIdx = b.MoneyIdx WHERE b.DominionTID IS NULL;
UPDATE b SET MoneyAmount += a.MoneyAmount FROM XDS_money_dominion_storage_tb a INNER JOIN money_dominion_storage_tb b ON a.DominionTID = b.DominionTID AND a.MoneyIdx = b.MoneyIdx;
INSERT INTO collection_item_account_complate_tb SELECT a.* FROM XDS_collection_item_account_complate_tb a LEFT JOIN collection_item_account_complate_tb b ON a.AccountUID = b.AccountUID  AND a.CollectionID = b.CollectionID WHERE b.AccountUID IS NULL;
DELETE b FROM collection_item_account_complate_tb a INNER JOIN collection_item_account_tb b ON a.AccountUID = b.AccountUID and a.CollectionID = b.CollectionID;
INSERT INTO collection_item_account_tb SELECT a.* FROM XDS_collection_item_account_tb a LEFT JOIN collection_item_account_tb b ON a.AccountUID = b.AccountUID  AND a.CollectionID = b.CollectionID AND a.Slot = b.Slot WHERE b.AccountUID IS NULL;
INSERT INTO pet_deck_tb SELECT * FROM XDS_pet_deck_tb
INSERT INTO pet_equip_item_tb SELECT * FROM XDS_pet_equip_item_tb
INSERT INTO item_tb SELECT a.* FROM XDS_item_tb a LEFT JOIN item_tb b ON a.ItemUID = b.ItemUID WHERE b.ItemUID IS NULL AND b.DeleteTime IS NULL;
INSERT INTO item_option_tb SELECT * FROM XDS_item_option_tb WHERE ItemUID IN(SELECT ItemUID FROM item_tb)
INSERT INTO dungeon_ticket_tb SELECT * FROM XDS_dungeon_ticket_tb
INSERT INTO cash_bag_character_tb SELECT * FROM XDS_cash_bag_character_tb
INSERT INTO buff_tb SELECT * FROM XDS_buff_tb
INSERT INTO mastery_step_tb SELECT * FROM XDS_mastery_step_tb
INSERT INTO mastery_tb SELECT * FROM XDS_mastery_tb
INSERT INTO great_building_tb SELECT * FROM XDS_great_building_tb
INSERT INTO mail_event_reward_tb SELECT * FROM XDS_mail_event_reward_tb
INSERT INTO dungeon_clear_tb SELECT * FROM XDS_dungeon_clear_tb
INSERT INTO collection_item_character_complate_tb SELECT * FROM XDS_collection_item_character_complate_tb
INSERT INTO collection_item_character_tb SELECT * FROM XDS_collection_item_character_tb
INSERT INTO equip_vehicle_ride_tb SELECT * FROM XDS_equip_vehicle_ride_tb
INSERT INTO vehicle_ride_tb SELECT * FROM XDS_vehicle_ride_tb
INSERT INTO event_tb SELECT a.* FROM XDS_event_tb a LEFT JOIN event_tb b ON a.CharacterUID = b.CharacterUID AND a.EventIdx = b.EventIdx WHERE b.CharacterUID IS NULL
INSERT INTO block_tb SELECT * FROM XDS_block_tb
INSERT INTO pet_tb SELECT * FROM XDS_pet_tb
INSERT INTO character_tb SELECT * FROM XDS_character_tb
INSERT INTO character_delete_reserve_tb SELECT * FROM XDS_character_delete_reserve_tb
INSERT INTO character_delete_tb SELECT * FROM XDS_character_delete_tb
INSERT INTO character_revival_tb SELECT * FROM XDS_character_revival_tb
INSERT INTO force_tb SELECT * FROM XDS_force_tb
INSERT INTO force_blood_tb SELECT * FROM XDS_force_blood_tb
INSERT INTO achievement_tb SELECT * FROM XDS_achievement_tb
INSERT INTO productbuycnt_character_tb SELECT a.* FROM XDS_productbuycnt_character_tb a LEFT JOIN productbuycnt_character_tb b ON a.CharacterUID = b.CharacterUID AND a.ProductIdx = b.ProductIdx WHERE b.CharacterUID IS NULL
INSERT INTO money_character_tb SELECT * FROM XDS_money_character_tb
INSERT INTO battle_pass_reward_tb SELECT * FROM XDS_battle_pass_reward_tb
INSERT INTO equip_costumehide_tb SELECT * FROM XDS_equip_costumehide_tb
INSERT INTO equip_item_tb SELECT a.* FROM XDS_equip_item_tb a LEFT JOIN equip_item_tb b ON a.CharacterUID = b.CharacterUID AND a.EquipSlot = b.EquipSlot AND a.Class = b.Class WHERE b.CharacterUID IS NULL
INSERT INTO battle_pass_mission_tb SELECT * FROM XDS_battle_pass_mission_tb
INSERT INTO costume_tb SELECT * FROM XDS_costume_tb
INSERT INTO skill_active_tb SELECT * FROM XDS_skill_active_tb
INSERT INTO customize_tb SELECT * FROM XDS_customize_tb
INSERT INTO customtitle_tb SELECT * FROM XDS_customtitle_tb
INSERT INTO skill_deck_tb SELECT * FROM XDS_skill_deck_tb
INSERT INTO quest_sub_tb SELECT * FROM XDS_quest_sub_tb
INSERT INTO quickslot_tb SELECT * FROM XDS_quickslot_tb
INSERT INTO quest_daily_tb SELECT * FROM XDS_quest_daily_tb
INSERT INTO playdata_tb SELECT * FROM XDS_playdata_tb
INSERT INTO quest_main_tb SELECT * FROM XDS_quest_main_tb
INSERT INTO item_holdoption_tb SELECT * FROM XDS_item_holdoption_tb
INSERT INTO battle_pass_info_tb SELECT * FROM XDS_battle_pass_info_tb
INSERT INTO quest_relation_tb SELECT * FROM XDS_quest_relation_tb
INSERT INTO quest_request_tb SELECT * FROM XDS_quest_request_tb
INSERT INTO tutorialclear_character_tb SELECT * FROM XDS_tutorialclear_character_tb
INSERT INTO quest_relation_reward_tb SELECT * FROM XDS_quest_relation_reward_tb
INSERT INTO gameoption_tb SELECT * FROM XDS_gameoption_tb
INSERT INTO fame_tb SELECT * FROM XDS_fame_tb
INSERT INTO timeticket_character_tb SELECT * FROM XDS_timeticket_character_tb
INSERT INTO eventdata_tb SELECT * FROM XDS_eventdata_tb
INSERT INTO waypoint_tb SELECT * FROM XDS_waypoint_tb
INSERT INTO quest_sub_clearcnt_tb SELECT * FROM XDS_quest_sub_clearcnt_tb
INSERT INTO equip_costume_tb SELECT * FROM XDS_equip_costume_tb a
INSERT INTO quest_daily_list_tb SELECT * FROM XDS_quest_daily_list_tb
INSERT INTO compose_fail_point_tb SELECT * FROM XDS_compose_fail_point_tb
INSERT INTO period_goods_tb SELECT * FROM XDS_period_goods_tb
INSERT INTO gacha_tb SELECT * FROM XDS_gacha_tb
INSERT INTO closed_training_tb SELECT * FROM XDS_closed_training_tb
INSERT INTO character_server_expedition_tb SELECT * FROM XDS_character_server_expedition_tb
INSERT INTO character_server_expedition_native_tb SELECT * FROM XDS_character_server_expedition_native_tb
INSERT INTO limit_drop_tb SELECT * FROM XDS_limit_drop_tb
INSERT INTO character_phase_tb SELECT * FROM XDS_character_phase_tb
INSERT INTO item_subcooltime_tb SELECT * FROM XDS_item_subcooltime_tb
INSERT INTO collection_siege_reg_time_tb SELECT * FROM XDS_collection_siege_reg_time_tb
INSERT INTO character_nft_tb SELECT * FROM XDS_character_nft_tb
INSERT INTO item_acquisition_path_tb SELECT * FROM XDS_item_acquisition_path_tb
INSERT INTO ads_tb SELECT a.* FROM XDS_ads_tb a LEFT JOIN ads_tb b ON a.CharacterUID = b.CharacterUID WHERE b.CharacterUID IS NULL
INSERT INTO draco_smelting_tb SELECT a.* FROM XDS_draco_smelting_tb a LEFT JOIN draco_smelting_tb b ON a.CharacterUID = b.CharacterUID WHERE b.CharacterUID IS NULL
INSERT INTO equip_luxury_costume_hide_tb SELECT * FROM XDS_equip_luxury_costume_hide_tb
INSERT INTO equip_luxury_costume_tb SELECT * FROM XDS_equip_luxury_costume_tb
INSERT INTO benediction_event_tb SELECT * FROM XDS_benediction_event_tb
INSERT INTO proud_wonder_tb SELECT * FROM XDS_proud_wonder_tb
INSERT INTO holy_stuff_grade_tb SELECT * FROM XDS_holy_stuff_grade_tb
INSERT INTO holy_stuff_slot_tb SELECT * FROM XDS_holy_stuff_slot_tb
INSERT INTO guild_tb SELECT * FROM XDS_guild_tb
INSERT INTO guild_supply_unlock_time SELECT * FROM XDS_guild_supply_unlock_time
INSERT INTO guild_shop_tb SELECT * FROM XDS_guild_shop_tb
INSERT INTO guild_shop_log_tb ([GuildUID], [ActionType], [LogTime], [Profile], [CharacterName], [CharacterUID], [GoodsIndex], [GoodsCount]) SELECT [GuildUID], [ActionType], [LogTime], [Profile], [CharacterName], [CharacterUID], [GoodsIndex], [GoodsCount] FROM XDS_guild_shop_log_tb ORDER BY LogUID
INSERT INTO guild_option_tb SELECT * FROM XDS_guild_option_tb
INSERT INTO guild_npc_shop_income_tb SELECT * FROM XDS_guild_npc_shop_income_tb
INSERT INTO guild_member_donation_weekly_tb SELECT * FROM XDS_guild_member_donation_weekly_tb
INSERT INTO guild_member_donation_daily_tb SELECT * FROM XDS_guild_member_donation_daily_tb
INSERT INTO guild_member_authority_tb SELECT * FROM XDS_guild_member_authority_tb
INSERT INTO guild_name_change_reserve_tb SELECT * FROM XDS_guild_name_change_reserve_tb
INSERT INTO guild_joinrequest_tb SELECT * FROM XDS_guild_joinrequest_tb
INSERT INTO guild_joininvite_tb SELECT * FROM XDS_guild_joininvite_tb
INSERT INTO guild_gift_tb SELECT * FROM XDS_guild_gift_tb
INSERT INTO guild_expedition_create_tb SELECT * FROM XDS_guild_expedition_create_tb
INSERT INTO guild_exedition_tb SELECT * FROM XDS_guild_exedition_tb
INSERT INTO guild_develop_tb SELECT * FROM XDS_guild_develop_tb
INSERT INTO guild_command_mark_tb SELECT * FROM XDS_guild_command_mark_tb
INSERT INTO character_guild_tb SELECT * FROM XDS_character_guild_tb
INSERT INTO character_guild_donation_tb SELECT * FROM XDS_character_guild_donation_tb;
INSERT INTO money_guild_tb SELECT * FROM XDS_money_guild_tb;
INSERT INTO unsealing_tb SELECT * FROM XDS_unsealing_tb;
INSERT INTO unsealing_support_tb SELECT * FROM XDS_unsealing_support_tb;
INSERT INTO quest_guild_list_tb SELECT * FROM XDS_quest_guild_list_tb;
INSERT INTO friend_request_tb SELECT * FROM XDS_friend_request_tb;
INSERT INTO friend_tb SELECT * FROM XDS_friend_tb;
INSERT INTO pk_history SELECT * FROM XDS_pk_history;
INSERT INTO pk_wanted(character_uid,nickname,class,end_type,combatpoint,guild_uid,guild_name,gulid_mark,guild_mark_edge,cumulative_count,prize_type,prize,fame_point,register_time,wanted_end_time) SELECT character_uid,nickname,class,end_type,combatpoint,guild_uid,guild_name,gulid_mark,guild_mark_edge,cumulative_count,prize_type,prize,fame_point,register_time,wanted_end_time FROM XDS_pk_wanted;
INSERT INTO sickness_recovery_tb SELECT * FROM XDS_sickness_recovery_tb;
INSERT INTO mail_character_tb SELECT a.* FROM XDS_mail_character_tb a LEFT JOIN mail_character_tb b ON a.CharacterMailUID = b.CharacterMailUID WHERE b.CharacterMailUID IS NULL
INSERT INTO mail_character_itemidx_tb SELECT a.* FROM XDS_mail_character_itemidx_tb a LEFT JOIN mail_character_itemidx_tb b ON a.CharacterMailUID = b.CharacterMailUID AND a.AttachSlot = b.AttachSlot WHERE b.CharacterMailUID IS NULL
INSERT INTO mail_character_money_tb SELECT * FROM XDS_mail_character_money_tb;
INSERT INTO character_guild_expedition_tb SELECT a.* FROM XDS_character_guild_expedition_tb a LEFT JOIN character_guild_expedition_tb b ON a.CharacterUID = b.CharacterUID AND a.GuildExpeditionID = b.GuildExpeditionID WHERE b.CharacterUID IS NULL;
INSERT INTO character_guild_receive_cost SELECT a.* FROM XDS_character_guild_receive_cost a LEFT JOIN character_guild_receive_cost b ON a.CharacterUID = b.CharacterUID AND a.MoneyIdx = b.MoneyIdx WHERE b.CharacterUID IS NULL;
INSERT INTO trade_register_tb SELECT * FROM XDS_trade_register_tb
INSERT INTO trade_log_tb([ComplateTime], [ItemUid], [CharacterUid], [ItemTid], [SmeltingLv], [StackCount], [State], [MoneyIdx], [MoneyAmount], [CalculateValue], [TradeTime], [TradeUid], [DecreaseSellTax], [TranceStep], [XDracoTradeState], [Collectable], [LogBuyCharacterUID], [LogIsDel], [RefineStep], [ItemLv], [ItemExp], [IsStampOption], [WorldID]) SELECT [ComplateTime], [ItemUid], [CharacterUid], [ItemTid], [SmeltingLv], [StackCount], [State], [MoneyIdx], [MoneyAmount], [CalculateValue], [TradeTime], [TradeUid], [DecreaseSellTax], [TranceStep], [XDracoTradeState], [Collectable], [LogBuyCharacterUID], [LogIsDel], [RefineStep], [ItemLv], [ItemExp], [IsStampOption], [WorldID] FROM XDS_trade_log_tb ORDER BY LogUid
INSERT INTO potential_tb SELECT * FROM XDS_potential_tb;
INSERT INTO guild_coop_mission_group_complete_tb SELECT * FROM XDS_guild_coop_mission_group_complete_tb;
INSERT INTO guild_coop_mission_group_tb SELECT * FROM XDS_guild_coop_mission_group_tb;
INSERT INTO guild_coop_mission_tb SELECT * FROM XDS_guild_coop_mission_tb;
INSERT INTO quest_cooperation_tb SELECT * FROM XDS_quest_cooperation_tb;
INSERT INTO cash_bag_character_gift_tb SELECT * FROM XDS_cash_bag_character_gift_tb;
INSERT INTO character_death_penalty_tb SELECT * FROM XDS_character_death_penalty_tb;						-- 사망복구
INSERT INTO character_death_penalty_item_tb SELECT * FROM XDS_character_death_penalty_item_tb;				-- 사망복구아이템
INSERT INTO painting_guild_trade_tb(GuildUID,CharacterUID,ItemID,ItemCount,Exchange_ItemID,Exchange_ItemCount,Exchange_Complete,Trade_Complete,Deleted,RegTime) SELECT GuildUID,CharacterUID,ItemID,ItemCount,Exchange_ItemID,Exchange_ItemCount,Exchange_Complete,Trade_Complete,Deleted,RegTime FROM XDS_painting_guild_trade_tb; -- 초상화
INSERT INTO black_dragon_dungeon_tb SELECT * FROM XDS_black_dragon_dungeon_tb;
INSERT INTO character_conquer_server_tb SELECT * FROM XDS_character_conquer_server_tb;
INSERT INTO shop_random_tb SELECT * FROM XDS_shop_random_tb;
INSERT INTO shop_randomlist_tb SELECT * FROM XDS_shop_randomlist_tb;
INSERT INTO item_make_agency_character_tb SELECT * FROM XDS_item_make_agency_character_tb;
INSERT INTO item_lv_tb SELECT * FROM XDS_item_lv_tb;
INSERT INTO magic_orb_deck_tb SELECT * FROM XDS_magic_orb_deck_tb;
INSERT INTO symbol_deck_tb SELECT * FROM XDS_symbol_deck_tb;
INSERT INTO shop_limit_character_tb SELECT * FROM XDS_shop_limit_character_tb;
INSERT INTO collection_book_character_complate_tb SELECT * FROM XDS_collection_book_character_complate_tb;
INSERT INTO popup_store_tb SELECT * FROM XDS_popup_store_tb;
INSERT INTO event_bingo_tb SELECT * FROM XDS_event_bingo_tb;
INSERT INTO dragon_gear_bless_tb SELECT * FROM XDS_dragon_gear_bless_tb;
INSERT INTO pray_tb SELECT * FROM XDS_pray_tb;
INSERT INTO item_passive_tb SELECT * FROM XDS_item_passive_tb;
INSERT INTO scripturehall_tb SELECT * FROM XDS_scripturehall_tb;
INSERT INTO scripturehall_item_tb SELECT * FROM XDS_scripturehall_item_tb;
INSERT INTO item_hold_passive_tb SELECT * FROM XDS_item_hold_passive_tb;
INSERT INTO item_holdoption_special_tb SELECT * FROM XDS_item_holdoption_special_tb;
INSERT INTO battle_pass_check_tb SELECT * FROM XDS_battle_pass_check_tb;
INSERT INTO productbuycnt_account_tb SELECT a.* FROM XDS_productbuycnt_account_tb a LEFT JOIN productbuycnt_account_tb b ON a.AccountUID = b.AccountUID AND a.ProductIdx = b.ProductIdx WHERE b.AccountUID IS NULL
INSERT INTO force_slump_tb SELECT * FROM XDS_force_slump_tb
INSERT INTO character_server_change_tb SELECT a.* FROM XDS_character_server_change_tb a LEFT JOIN character_server_change_tb b ON a.CharacterUID = b.CharacterUID WHERE b.CharacterUID IS NULL
INSERT INTO item_make_xdraco_limit_character_tb SELECT * FROM XDS_item_make_xdraco_limit_character_tb
INSERT INTO heaven_training_group_tb SELECT * FROM XDS_heaven_training_group_tb
INSERT INTO heaven_training_node_tb SELECT * FROM XDS_heaven_training_node_tb
INSERT INTO heaven_training_option_tb SELECT * FROM XDS_heaven_training_option_tb
INSERT INTO divine_dragon_tb SELECT * FROM XDS_divine_dragon_tb
INSERT INTO contents_option_tb SELECT * FROM XDS_contents_option_tb
INSERT INTO mission_data_tb SELECT * FROM XDS_mission_data_tb
INSERT INTO mission_pass_tb SELECT * FROM XDS_mission_pass_tb
INSERT INTO cash_shop_buy_item SELECT * FROM XDS_cash_shop_buy_item
INSERT INTO heaven_training_support_tb SELECT * FROM XDS_heaven_training_support_tb
INSERT INTO guild_point_tb SELECT * FROM XDS_guild_point_tb;
DECLARE @NewHistoryUID BIGINT SELECT @NewHistoryUID = MAX(HistoryUID)+1 FROM guild_history_tb
UPDATE a SET a.NewHistoryUID = RN FROM XDS_guild_history_tb a INNER JOIN ( SELECT ROW_NUMBER() OVER ( ORDER BY HistoryUID ) + @NewHistoryUID AS RN, * FROM XDS_guild_history_tb ) b ON a.GuildUID = b.GuildUID AND a.HistoryUID = b.HistoryUID AND a.HistoryGroupID = b.HistoryGroupID
UPDATE a SET HistoryUID = NewHistoryUID FROM XDS_guild_history_param_tb a INNER JOIN XDS_guild_history_tb b ON a.HistoryUID = b.HistoryUID;
UPDATE a SET HistoryUID = NewHistoryUID FROM XDS_guild_history_money_tb a INNER JOIN XDS_guild_history_tb b ON a.HistoryUID = b.HistoryUID;
SET IDENTITY_INSERT guild_history_tb ON
INSERT INTO guild_history_tb ([GuildUID], [HistoryUID], [RegDate], [HistoryGroupID], [HistoryIndex], [CharacterUID], [HistorySubGroupID]) SELECT [GuildUID], [NewHistoryUID], [RegDate], [HistoryGroupID], [HistoryIndex], [CharacterUID], [HistorySubGroupID] FROM XDS_guild_history_tb
SET IDENTITY_INSERT guild_history_tb OFF
INSERT INTO guild_history_param_tb SELECT * FROM XDS_guild_history_param_tb
INSERT INTO guild_history_money_tb SELECT * FROM XDS_guild_history_money_tb
