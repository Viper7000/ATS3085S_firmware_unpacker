Контейнеры ресурсов формата SDFS. Бывают в файлах sdfs.bin или sdfs_*.bin. Есть и внутри прошики (f) и внутри upgrade.fw (u) 
Под определенным названием находятся определенные ресурсы, которые заливаются в определенную область памяти

### sdfs.bin (u)
* alcfg.bin
* bttbl.bin
* bt_pth.bin
* bt_rf.bin
* cfg_mic.bin
* defcfg.bin
* extcfg.bin
* sdfs.txt - содержит 1234567890
* siren.act
* usrcfg.bin

### sdfs_a.bin (f,u)
* c****_res - циферблаты  
       ...
* ic****_res - AOD (C191)  
       ...
* callring.act
* gly_api.env - токены доступа к интернет ресурсам
* khmer.ttf - шрифт (?)
* sec_res - картинки ресурсов
* video_res - картинки для видеофайлов  
* on.avi - видео включения (Tank T6)
* off.avi - видео выключения (Tank T6)

### sdfs_b.bin (f) - шрифты
* aria.ttf
* burmese.ttf
* chose.ttf
* harmony.ttf
* khmer.ttf
* latte.ttf
* vfont.ttf

### sdfs_c.bin (f)
* other_res - кртинки интерфейса

### sdfs_d.bin (f)
* c****_res - циферблаты  
       ...
* ic**_res - AOD  
       ...
* ic****_res - AOD  
       ...
* pointer* - циферблаты, только стрелки  
       ...
* ai_b.bin - запакована картинка AI циферблата
* ai_t.bin - картинка AI циферблата размыта, превьюв
* u_d_b.bin - запакована картинка фотоциферблата
* u_d_t.bin - картинка фотоциферблата размыта, превьюв
* video_b.bin - запакована картинка видеоциферблата
* video_t.bin - картинка видеоциферблата размыта, превьюв
* uc*  
       ... (?)
* arabic.ttf (C191)
* puhui-r.ttf (C191)
* roboto.ttf (C191)
* bdbeads.pkg (C191)
* calendar.pkg (C191)
* deepseek.pkg (C191)
* emoji.fnt (C191)
* puhui.fnt (C191)
* faces (C191)
* map.pkg (C191)
* music163.pkg (C191)
* stock.pkg (C191)
* store.pkg (C191)
* transl.pkg (C191)
* travel.pkg (C191)
* weather.pkg (C191)
* woodfish.pkg (C191)
* wxreply.pkg (C191)
* ximalaya.pkg (C191)

### sdfs_e.bin (f,u)
* logo.res - много блоков заполненный либо "E3 18" либо "00" либо какими-то повторяющимися байтами
* on.avi - видео включения
* off.avi - видео выключения

### sdfs_f.bin (u) - мелодии звонка и тест
* ring0.mp3
* ring1.mp3
* ring2.mp3
* ring3.mp3
* ring4.mp3
* ring5.mp3
* ring6.mp3
* ring7.mp3
* ring8.mp3
* siren.mp3
* test.mp3  
* ding.mp3 (Tank T6)
* dong.mp3 (Tank T6)  
* dice.mp3 (C191)
* drain.mp3 (C191)
* gun.mp3 (C191)
* plam.mp3 (C191)
* sword.mp3 (C191)

### sdfs_k.bin (u)
* admusic.dsp - вероятно какие-то звуковые файлы
* adsilk.dsp
* aeopus.dsp
* alarm.act
* alarm1.act (?)
* bttbl.bin
* bt_rf.bin
* charge1.act (?)
* find.act
* harmony.ttf
* m_**-**.hex - бинарники связанные с языками (m_ru-ru.hex, m_uk-ua.hex)  
       ...
* r_**-**.hex - бинарники связанные с языками (r_ru-ru.hex, r_uk-ua.hex)  
       ...
* sdfs.txt
* tst.bin
















