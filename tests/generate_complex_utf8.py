#!/usr/bin/env python

"""
    Generate lots of strings with 2, 3, and 4-bytes utf-8 codes
    Dumps them into an ascii ldif file
"""

I_CAN_EAT_GLASS = {
    'emoji': "😁😂😃😄😅😆😠😡😢😣😤😥😨😩😪🚉🚌🚏🚑🚒🚓🚕🚗🚙🚚🚢🚤🚥🚧🚨🚻🚼🚽🚾🛀🆕🆖🆗🆘🆙🆚🈁🈂🈚🈯🈹🈺🉐🉑8⃣9⃣7⃣6⃣1⃣0",
    'sanskrit': "काचं शक्नोम्यत्तुम् । नोपहिनस्ति माम् ॥",
    'sanskrit_standard': "kācaṃ śaknomyattum; nopahinasti mām.",
    'greek': {
        'classic': "ὕαλον ϕαγεῖν δύναμαι· τοῦτο οὔ με βλάπτει.",
        'monotonic': "Μπορώ να φάω σπασμένα γυαλιά χωρίς να πάθω τίποτα.",
        'polytonic': "Μπορῶ νὰ φάω σπασμένα γυαλιὰ χωρὶς νὰ πάθω τίποτα."
    },
    'latin': "Vitrum edere possum; mihi non nocet.",
    'french': {
        'old': "Je puis mangier del voirre. Ne me nuit.",
        'standard': "Je peux manger du verre, ça ne me fait pas mal.",
        'occitan': "Pòdi manjar de veire, me nafrariá pas.",
        'quebec': "J'peux manger d'la vitre, ça m'fa pas mal.",
        'walloon': "Dji pou magnî do vêre, çoula m' freut nén må.",
        'picard': "Ch'peux mingi du verre, cha m'foé mie n'ma."
    },
    'haiti': "Mwen kap manje vè, li pa blese'm.",
    'spanish': {
        'basque': "Kristala jan dezaket, ez dit minik ematen.",
        'catalan': "Puc menjar vidre, que no em fa mal.",
        'castiliano': "Puedo comer vidrio, no me hace daño.",
        'aragones': "Puedo minchar beire, no me'n fa mal .",
        'galician': "Eu podo xantar cristais e non cortarme."
    },
    'portuguese': {
        'standard': "Posso comer vidro, não me faz mal.",
        'brazilian': "Posso comer vidro, não me machuca.",
        'caboverdiano': "M' podê cumê vidru, ca ta maguâ-m'.",
        'papiamentu': "Ami por kome glas anto e no ta hasimi daño."
    },
    'italian': {
        'standard': "Posso mangiare il vetro e non mi fa male.",
        'milanese': "Sôn bôn de magnà el véder, el me fa minga mal.",
        'roman': "Me posso magna' er vetro, e nun me fa male.",
        'napoletano': "M' pozz magna' o'vetr, e nun m' fa mal.",
        'venetian': "Mi posso magnare el vetro, no'l me fa mae.",
        'genovese': "Pòsso mangiâ o veddro e o no me fà mâ.",
        'sicilian': "Puotsu mangiari u vitru, nun mi fa mali.",
        'romansch': "Jau sai mangiar vaider, senza che quai fa donn a mai."
    },
    'romanian': "Pot să mănânc sticlă și ea nu mă rănește.",
    'esperanto': "Mi povas manĝi vitron, ĝi ne damaĝas min.",
    'english': {
        'standard': "I can eat glass and it doesn't hurt me.",
        'cornish': "Mý a yl dybry gwéder hag éf ny wra ow ankenya.",
        'welsh': "Dw i'n gallu bwyta gwydr, 'dyw e ddim yn gwneud dolur i mi.",
        'gaelic': "Foddym gee glonney agh cha jean eh gortaghey mee.",
        'old_irish_ogham': "᚛᚛ᚉᚑᚅᚔᚉᚉᚔᚋ ᚔᚈᚔ ᚍᚂᚐᚅᚑ ᚅᚔᚋᚌᚓᚅᚐ᚜",
        'old_irish_latin': "Con·iccim ithi nglano. Ním·géna.",
        'irish': "Is féidir liom gloinne a ithe. Ní dhéanann sí dochar ar bith dom.",
        'ulster_gaelic': "Ithim-sa gloine agus ní miste damh é.",
        'scottish_gaelic': "S urrainn dhomh gloinne ithe; cha ghoirtich i mi.",
        'runes': "ᛁᚳ᛫ᛗᚨᚷ᛫ᚷᛚᚨᛋ᛫ᛖᚩᛏᚪᚾ᛫ᚩᚾᛞ᛫ᚻᛁᛏ᛫ᚾᛖ᛫ᚻᛖᚪᚱᛗᛁᚪᚧ᛫ᛗᛖ᛬",
        'anglo_saxon': "Ic mæg glæs eotan ond hit ne hearmiað me.",
        'middle': "Ich canne glas eten and hit hirtiþ me nouȝt.",
        'ipa': "[aɪ kæn iːt glɑːs ænd ɪt dɐz nɒt hɜːt miː] (Received Pronunciation)",
        'braille': "⠊⠀⠉⠁⠝⠀⠑⠁⠞⠀⠛⠇⠁⠎⠎⠀⠁⠝⠙⠀⠊⠞⠀⠙⠕⠑⠎⠝⠞⠀⠓⠥⠗⠞⠀⠍⠑",
        'jamaican': "Mi kian niam glas han i neba hot mi.",
        'lalland_scots': "Ah can eat gless, it disnae hurt us."
    },
    'gothic': "ЌЌЌ ЌЌЌЍ Ќ̈ЍЌЌ, ЌЌ ЌЌЍ ЍЌ ЌЌЌЌ ЌЍЌЌЌЌЌ.",
    'norse': {
        'runes': "ᛖᚴ ᚷᛖᛏ ᛖᛏᛁ ᚧ ᚷᛚᛖᚱ ᛘᚾ ᚦᛖᛋᛋ ᚨᚧ ᚡᛖ ᚱᚧᚨ ᛋᚨᚱ",
        'old_latin': "Ek get etið gler án þess að verða sár.",
        'standard': "Eg kan eta glas utan å skada meg.",
        'bokmal': "Jeg kan spise glass uten å skade meg.",
        'faroese': "Eg kann eta glas, skaðaleysur.",
        'icelandic': "Ég get etið gler án þess að meiða mig.",
        'svenska': "Jag kan äta glas utan att skada mig.",
        'dansk': "Jeg kan spise glas, det gør ikke ondt på mig.",
        'sonderjysk': "Æ ka æe glass uhen at det go mæ naue."
    },
    'german': {
        'frysk': "Ik kin glês ite, it docht me net sear.",
        'nederlands': "Ik kan glas eten, het doet mĳ geen kwaad.",
        'plat': "Iech ken glaas èèse, mer 't deet miech jing pieng.",
        'afrikaans': "Ek kan glas eet, maar dit doen my nie skade nie.",
        'luxemburgish': "Ech kan Glas iessen, daat deet mir nët wei.",
        'standard': "Ich kann Glas essen, ohne mir zu schaden.",
        'ruhrdeutsch': "Ich kann Glas verkasematuckeln, ohne dattet mich wat jucken tut.",
        'langenfelder_platt': "Isch kann Jlaas kimmeln, uuhne datt mich datt weh dääd.",
        'lusatian': "Ich koann Gloos assn und doas dudd merr ni wii.",
        'odenwalderisch': "Iech konn glaasch voschbachteln ohne dass es mir ebbs daun doun dud.",
        'sachsisch': "'sch kann Glos essn, ohne dass'sch mer wehtue.",
        'pfalzisch': "Isch konn Glass fresse ohne dasses mer ebbes ausmache dud.",
        'schwabisch': "I kå Glas frässa, ond des macht mr nix!",
        'voralberg': "I ka glas eassa, ohne dass mar weh tuat.",
        'bayrisch': "I koh Glos esa, und es duard ma ned wei.",
        'allemannisch': "I kaun Gloos essen, es tuat ma ned weh.",
        'zurich': "Ich chan Glaas ässe, das schadt mir nöd.",
        'luzern': "Ech cha Glâs ässe, das schadt mer ned."
    },
    'hungarian': "Meg tudom enni az üveget, nem lesz tőle bajom.",
    'suomi': "Voin syödä lasia, se ei vahingoita minua.",
    'erzian': "Мон ярсан суликадо, ды зыян эйстэнзэ а ули.",
    'karelian': {
        'north': "Mie voin syvvä lasie ta minla ei ole kipie.",
        'south': "Minä voin syvvä st'oklua dai minule ei ole kibie."
    },
    'estonian': "Ma võin klaasi süüa, see ei tee mulle midagi.",
    'latvian': "Es varu ēst stiklu, tas man nekaitē.",
    'lithuanian': "Aš galiu valgyti stiklą ir jis manęs nežeidžia",
    'czech': "Mohu jíst sklo, neublíží mi.",
    'slovak': "Môžem jesť sklo. Nezraní ma.",
    'polska': "Mogę jeść szkło i mi nie szkodzi.",
    'slovenian': "Lahko jem steklo, ne da bi mi škodovalo.",
    'bosnian': {
        'latin': "Ja mogu jesti staklo, i to mi ne šteti.",
        'cyrillic': "Ја могу јести стакло, и то ми не штети."
    },
    'macedonian': "Можам да јадам стакло, а не ме штета.",
    'russian': "Я могу есть стекло, оно мне не вредит.",
    'belarusian': {
        'cyrillic': "Я магу есці шкло, яно мне не шкодзіць.",
        'lacinka': "Ja mahu jeści škło, jano mne ne škodzić."
    },
    'ukrainian': "Я можу їсти скло, і воно мені не зашкодить.",
    'bulgarian': "Мога да ям стъкло, то не ми вреди.",
    'georgian': "მინას ვჭამ და არა მტკივა.",
    'armenian': "Կրնամ ապակի ուտել և ինծի անհանգիստ չըներ։",
    'albanian': "Unë mund të ha qelq dhe nuk më gjen gjë.",
    'turkish': {
        'latin': "Cam yiyebilirim, bana zararı dokunmaz.",
        'ottoman': "جام ييه بلورم بڭا ضررى طوقونمز"
    },
    'bangla': "আমি কাঁচ খেতে পারি, তাতে আমার কোনো ক্ষতি হয় না।",
    'marathi': "मी काच खाऊ शकतो, मला ते दुखत नाही.",
    'kannada': "ನನಗೆ ಹಾನಿ ಆಗದೆ, ನಾನು ಗಜನ್ನು ತಿನಬಹುದು",
    'hindi': "मैं काँच खा सकता हूँ और मुझे उससे कोई चोट नहीं पहुंचती.",
    'tamil': "நான் கண்ணாடி சாப்பிடுவேன், அதனால் எனக்கு ஒரு கேடும் வராது.",
    'telugu': "నేను గాజు తినగలను మరియు అలా చేసినా నాకు ఏమి ఇబ్బంది లేదు",
    'sinhalese': "මට වීදුරු කෑමට හැකියි. එයින් මට කිසි හානියක් සිදු නොවේ.",
    'urdu': "میں کانچ کھا سکتا ہوں اور مجھے تکلیف نہیں ہوتی ۔",
    'pashto': "زه شيشه خوړلې شم، هغه ما نه خوږوي",
    'farsi': ".من می توانم بدونِ احساس درد شيشه بخورم",
    'arabic': "أنا قادر على أكل الزجاج و هذا لا يؤلمني.",
    'maltese': "Nista' niekol il-ħġieġ u ma jagħmilli xejn.",
    'hebrew': "אני יכול לאכול זכוכית וזה לא מזיק לי.",
    'yiddish': "איך קען עסן גלאָז און עס טוט מיר נישט װײ.",
    'twi': "Metumi awe tumpan, ɜnyɜ me hwee.",
    'hausa': {
        'latin': "Inā iya taunar gilāshi kuma in gamā lāfiyā.",
        'ajami': "إِنا إِىَ تَونَر غِلَاشِ كُمَ إِن غَمَا لَافِىَا"
    },
    'yoruba': "Mo lè je̩ dígí, kò ní pa mí lára.",
    'lingala': "Nakokí kolíya biténi bya milungi, ekosála ngáí mabé tɛ́.",
    'swahili': "Naweza kula bilauri na sikunyui.",
    'malay': "Saya boleh makan kaca dan ia tidak mencederakan saya.",
    'tagalog': "Kaya kong kumain nang bubog at hindi ako masaktan.",
    'chamorro': "Siña yo' chumocho krestat, ti ha na'lalamen yo'.",
    'fijian': "Au rawa ni kana iloilo, ia au sega ni vakacacani kina.",
    'javanese': "Aku isa mangan beling tanpa lara.",
    'burmese': "က္ယ္ဝန္‌တော္‌၊က္ယ္ဝန္‌မ မ္ယက္‌စားနုိင္‌သည္‌။ ၎က္ရောင္‌့ ထိခုိက္‌မ္ဟု မရ္ဟိပာ။ (9)",
    'vietnamese': {
        'latin': "Tôi có thể ăn thủy tinh mà không hại gì.",
        'classic': "些 ࣎ 世 咹 水 晶 ও 空 ࣎ 害 咦"
    },
    'khmer': "ខ្ញុំអាចញុំកញ្ចក់បាន ដោយគ្មានបញ្ហារ",
    'lao': "ຂອ້ຍກິນແກ້ວໄດ້ໂດຍທີ່ມັນບໍ່ໄດ້ເຮັດໃຫ້ຂອ້ຍເຈັບ.",
    'thai': "ฉันกินกระจกได้ แต่มันไม่ทำให้ฉันเจ็บ",
    'mongolian': {
        'cyrillic': "Би шил идэй чадна, надад хортой биш",
        'classic': "ᠪᠢ ᠰᠢᠯᠢ ᠢᠳᠡᠶᠦ ᠴᠢᠳᠠᠨᠠ ᠂ ᠨᠠᠳᠤᠷ ᠬᠣᠤᠷᠠᠳᠠᠢ ᠪᠢᠰᠢ"
    },
    'nepali': "﻿म काँच खान सक्छू र मलाई केहि नी हुन्‍न् ।",
    'tibetan': "ཤེལ་སྒོ་ཟ་ནས་ང་ན་གི་མ་རེད།",
    'chinese': {
        'simplified': "我能吞下玻璃而不伤身体。",
        'traditional': "我能吞下玻璃而不傷身體。"
    },
    'taiwanese': "Góa ē-tàng chia̍h po-lê, mā bē tio̍h-siong.",
    'japanese': "私はガラスを食べられます。それは私を傷つけません。",
    'korean': "나는 유리를 먹을 수 있어요. 그래도 아프지 않아요",
    'bislama': "Mi save kakae glas, hemi no save katem mi.",
    'hawaiian': "Hiki iaʻu ke ʻai i ke aniani; ʻaʻole nō lā au e ʻeha.",
    'marquesan': "E koʻana e kai i te karahi, mea ʻā, ʻaʻe hauhau.",
    'inuktitut': "ᐊᓕᒍᖅ ᓂᕆᔭᕌᖓᒃᑯ ᓱᕋᙱᑦᑐᓐᓇᖅᑐᖓ",
    'chinook_jargon': "Naika məkmək kakshət labutay, pi weyk ukuk munk-sik nay.",
    'navajo': "Tsésǫʼ yishą́ągo bííníshghah dóó doo shił neezgai da.",
    'lojban': "mi kakne le nu citka le blaci .iku'i le se go'i na xrani mi"
}

if __name__ == '__main__':
    import base64
    import os
    import sys

    def print_values(string_dict, ofile=sys.stdout):
        def print_value(value):
            r = ['value:']
            try:
                s = value.encode().decode('ascii')
                value = s
            except UnicodeDecodeError:
                r.append(':')
                value = base64.standard_b64encode(value.encode()).decode('ascii')
            while len(value) > 0:
                first_64 = value[:64]
                r += [' ', first_64]
                if len(value) > 64:
                    value = value[64:]
                    r.append("\n")
                    while first_64.endswith(' '):
                        r.append(' ')
                        first_64 = first_64[:-1]
                else:
                    value = []
            print(''.join(r), file=ofile)

        indx = 0
        for k in sorted(string_dict.keys()):
            indx += 1
            v = string_dict[k]
            try:
                if isinstance(v, str):
                    print("dn: sn=" + k, file=ofile)
                    print("sn: " + k, file=ofile)
                    print("indx: %d" % (1000 * indx), file=ofile)
                    print_value(v)
                    print("", file=ofile)
                else:
                    indx2 = 0
                    for kk in sorted(v.keys()):
                        indx2 += 1
                        vv = v[kk]
                        print("dn: sn=%s, cn=%s" % (k, kk), file=ofile)
                        print("sn: " + k, file=ofile)
                        print("cn: " + kk, file=ofile)
                        print("indx: %d" % ((1000 * indx) + indx2), file=ofile)
                        print_value(vv)
                        print("", file=ofile)
            except UnicodeEncodeError as uee:
                print('%3d (%s) (%s)' % (indx,k,v))
                print(uee)


    fn = os.path.join(os.path.dirname(__file__),'resources','utf8.ldif')
    with open(fn, 'w', encoding='ascii') as g:
        print_values(I_CAN_EAT_GLASS, g)


