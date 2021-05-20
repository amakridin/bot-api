select chat_id from(
select chat_id
from bot_chat_list 
where typ=999
  and issue is not null
  and chat_id not in (select chat_id from bot_chat_list where typ<>999)
order by recordid desc)
where rownum<2
