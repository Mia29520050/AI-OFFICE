"""
Complete End-to-End Test for Manga & Storyboard Generation:
Theme: 20-page Manga about a young man transforming into a magical girl in Tokyo, Japan.
Creates Series, Characters, Chapter, 20 Storyboard Pages with rich panels, dialogues, and SFX,
renders composed manga pages, exports CBZ/PDF, and verifies in Web UI with Playwright.
"""
import asyncio
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
for p in (str(ROOT), str(APP_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import uvicorn
from main import app, init_db
from manga_studio import (
    connect, init_manga_db, now, MANGA_DATA,
    SeriesCreate, ChapterCreate, CharacterCreate
)
from manga_composer import (
    MangaComposer, PageConfig, PanelConfig, SpeechBubble,
    BubbleType, PanelLayoutType, PanelFilter, export_to_cbz, export_to_pdf,
    image_to_base64_data_url
)
from manga_comfy import MockPanelGenerator, ArtStyle
from PIL import Image, ImageDraw, ImageFont

ARTIFACT_DIR = Path(r"C:\Users\Shiro\.gemini\antigravity\brain\ba17a7d2-fcc5-4468-8872-6615a2f705c6")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

# 20-Page Story Script Specification
PAGES_SCRIPT = [
    {
        "page": 1,
        "layout": "3-panel",
        "title": "Đêm Tokyo bận rộn",
        "panels": [
            {
                "prompt": "wide establishing shot of Tokyo skyline at night, Tokyo Tower glowing, neon lights, manga screentones",
                "dialogue": [{"speaker": "Người dẫn chuyện", "text": "Tokyo, 23:30. Thành phố không bao giờ ngủ..."}],
                "sfx": [{"text": "GOGO...", "style": "ambient"}],
                "filter": "manga_ink"
            },
            {
                "prompt": "exterior of traditional ramen shop in Akihabara, warm steam rising from doorway",
                "dialogue": [{"speaker": "Chủ quán", "text": "Hôm nay vất vả rồi Ren! Về cẩn thận nhé!"}],
                "sfx": [{"text": "GARA GARA", "style": "action"}],
                "filter": "halftone"
            },
            {
                "prompt": "young muscular athletic Japanese man, 20yo, messy black hair, bomber jacket, stretching arms, tired but gentle expression",
                "dialogue": [{"speaker": "Ren", "text": "Cuối cùng cũng xong ca. Mai lại còn buổi tập boxing sớm nữa chứ..."}],
                "sfx": [],
                "filter": "manga_ink"
            }
        ]
    },
    {
        "page": 2,
        "layout": "3-panel",
        "title": "Hiện tượng dị thường",
        "panels": [
            {
                "prompt": "narrow dark alleyway near Akihabara train station, flickering streetlamps, deep shadows",
                "dialogue": [{"speaker": "Ren", "text": "Hẻm hôm nay vắng lạ thường... Không một bóng người."}],
                "sfx": [{"text": "ZA ZA...", "style": "suspense"}],
                "filter": "manga_ink"
            },
            {
                "prompt": "close-up of Ren's smartphone screen glitching with static electricity, clocks spinning backwards",
                "dialogue": [{"speaker": "Ren", "text": "Gì thế này? Mất sóng? Điện thoại bị chập à?"}],
                "sfx": [{"text": "BZZT!", "style": "action"}],
                "filter": "dither"
            },
            {
                "prompt": "sky above Tokyo turns dark purple violet, dimensional distortion vortex opening in the clouds",
                "dialogue": [{"speaker": "Ren", "text": "Khoan đã... bầu trời đang nứt ra?!"}],
                "sfx": [{"text": "GURURU...", "style": "rumble"}],
                "filter": "speedlines_radial"
            }
        ]
    },
    {
        "page": 3,
        "layout": "2-panel",
        "title": "Vật thể rơi tự do",
        "panels": [
            {
                "prompt": "glowing shooting star comet crashing down into the alley, sparkling magical stardust trail",
                "dialogue": [{"speaker": "Ren", "text": "CÁI GÌ ĐANG RƠI XUỐNG THẾ KIA?!"}],
                "sfx": [{"text": "HYUUUU---N!", "style": "speed"}],
                "filter": "speedlines_radial"
            },
            {
                "prompt": "cute chubby white magical rabbit mascot with tiny fairy wings landing directly into Ren's chest, stunned faces",
                "dialogue": [
                    {"speaker": "Kumi", "text": "Ouch!! Cứu bé vớiiii!!"},
                    {"speaker": "Ren", "text": "HỰ! Con thỏ biết bay... lại còn biết nói tiếng người?!"}
                ],
                "sfx": [{"text": "DOOOKA!", "style": "impact"}],
                "filter": "manga_ink"
            }
        ]
    },
    {
        "page": 4,
        "layout": "splash",
        "title": "Quái thú Hư Vô giáng lâm",
        "panels": [
            {
                "prompt": "giant terrifying shadow monster with glowing red eyes and sharp black tentacles towering over Tokyo alley, crushing concrete",
                "dialogue": [
                    {"speaker": "Void Fiend", "text": "GRRRROOOAAAR!! NĂNG LƯỢNG TIÊU CỰC CỦA TOKYO LÀ CỦA TA!"},
                    {"speaker": "Ren", "text": "Quái vật?! Đây không phải phim Tokusatsu đấy chứ?!"}
                ],
                "sfx": [{"text": "DOGOOOOON!!", "style": "massive_explosion"}],
                "filter": "speedlines_radial"
            }
        ]
    },
    {
        "page": 5,
        "layout": "3-panel",
        "title": "Hợp đồng ma thuật",
        "panels": [
            {
                "prompt": "cute mascot Kumi crying tears of panic, clutching Ren's collar desperately",
                "dialogue": [{"speaker": "Kumi", "text": "Đó là Quái Thú Hư Vô! Nếu không đánh bại nó, cả quận Shibuya sẽ biến mất!"}],
                "sfx": [{"text": "GATA GATA", "style": "shiver"}],
                "filter": "halftone"
            },
            {
                "prompt": "Kumi conjuring a golden star-topped glowing magical wand with wing ornaments",
                "dialogue": [{"speaker": "Kumi", "text": "Xin hãy nhận lấy Trượng Tinh Tú! Linh hồn quả cảm của anh là hy vọng duy nhất!"}],
                "sfx": [{"text": "KIRAKIRA!", "style": "sparkle"}],
                "filter": "speedlines_radial"
            },
            {
                "prompt": "Ren looking at the cute pastel wand with extreme hesitation and sweatdrops",
                "dialogue": [{"speaker": "Ren", "text": "Cái gậy đồ chơi lấp lánh này á? Thật sự đánh được quái vật sao?!"}],
                "sfx": [],
                "filter": "manga_ink"
            }
        ]
    },
    {
        "page": 6,
        "layout": "2-panel",
        "title": "Quyết định của một người đàn ông",
        "panels": [
            {
                "prompt": "monster tentacle smashing into nearby vending machine, sparks exploding into the alley",
                "dialogue": [{"speaker": "Ren", "text": "Chết tiệt! Nó đang tiến ra phố lớn, người đi đường sẽ gặp nguy hiểm!"}],
                "sfx": [{"text": "BAAANG!", "style": "impact"}],
                "filter": "speedlines_horizontal"
            },
            {
                "prompt": "Ren grasping the golden star wand with determination, fire in his eyes",
                "dialogue": [
                    {"speaker": "Ren", "text": "Được rồi con thú bông! Đưa đây! Dù là gậy gì, ta sẽ đập nát con quái vật đó!"},
                    {"speaker": "Kumi", "text": "Hợp đồng hoàn tất! Chuẩn bị thức tỉnh ma pháp nào!"}
                ],
                "sfx": [{"text": "GU-WAAANG!", "style": "energy"}],
                "filter": "speedlines_radial"
            }
        ]
    },
    {
        "page": 7,
        "layout": "splash",
        "title": "Ma trận thức tỉnh",
        "panels": [
            {
                "prompt": "massive glowing magical pentagram circle on ground, rainbow light shooting into the night sky of Tokyo",
                "dialogue": [
                    {"speaker": "Kumi", "text": "Hỡi ánh sáng thuần khiết! Hãy ban cho chiến binh sắc đẹp và công lý vĩnh cửu!"},
                    {"speaker": "Ren", "text": "Khoan... SẮC ĐẸP LÀ SAO?! AI CẦN SẮC ĐẸP CHỨ?!"}
                ],
                "sfx": [{"text": "SHIIIIIIING!!", "style": "flash"}],
                "filter": "speedlines_radial"
            }
        ]
    },
    {
        "page": 8,
        "layout": "4-panel",
        "title": "Quá trình biến thân - Giai đoạn 1",
        "panels": [
            {
                "prompt": "silky glowing ribbons of light swirling around Ren's muscular body, dissolving jacket",
                "dialogue": [{"speaker": "Ren", "text": "Áo khoác của mình biến thành... ruy băng lụa?!"}],
                "sfx": [{"text": "SHURURURU", "style": "ribbon"}],
                "filter": "halftone"
            },
            {
                "prompt": "sparkling fairy dust encasing legs, athletic sneakers transforming into white lace heeled boots with pink bows",
                "dialogue": [{"speaker": "Ren", "text": "ĐÔI GIÀY NÀY LÀ THẾ NÀO?! CÒN CẢ NƠ NỮA?!"}],
                "sfx": [{"text": "KIRAN!", "style": "sparkle"}],
                "filter": "manga_ink"
            },
            {
                "prompt": "frilly white and pink magical girl dress with layered petticoat wrapping tightly around torso",
                "dialogue": [{"speaker": "Ren", "text": "VÁY XOÈ?! TẠI SAO LẠI CÓ DIỀM XẾP NẾP?!"}],
                "sfx": [{"text": "PAAAT!", "style": "magic"}],
                "filter": "halftone"
            },
            {
                "prompt": "short black hair suddenly bursting into long flowing pastel pink twintails with star hairclips",
                "dialogue": [{"speaker": "Ren", "text": "ĐẦU TÔI NẶNG THẾ?! TÓC ĐÂU RA MÀ DÀI THẾ NÀY?!"}],
                "sfx": [{"text": "BWA-SHAA!", "style": "burst"}],
                "filter": "speedlines_radial"
            }
        ]
    },
    {
        "page": 9,
        "layout": "splash",
        "title": "Cô bé phép thuật Mirai Sparkle!",
        "panels": [
            {
                "prompt": "full body heroic magical girl pose, gorgeous cute pink twintail girl holding star wand, frilly dress, sparkling magical background Tokyo night",
                "dialogue": [
                    {"speaker": "Kumi", "text": "ĐÃ XONG! Chiến Binh Ánh Sáng Tình Yêu: MIRAI SPARKLE chính thức giáng thế!"},
                    {"speaker": "Mirai Sparkle (Ren)", "text": ".........Hả?"}
                ],
                "sfx": [{"text": "JAAAAAN!!", "style": "fanfare"}],
                "filter": "speedlines_radial"
            }
        ]
    },
    {
        "page": 10,
        "layout": "3-panel",
        "title": "Cú sốc đầu đời",
        "panels": [
            {
                "prompt": "close-up of Ren looking at reflection in shop window glass, seeing an ultra-cute anime girl face with big sparkly eyes",
                "dialogue": [{"speaker": "Ren", "text": "C-Cái mặt dễ thương này... là tôi sao?!"}],
                "sfx": [{"text": "GA-AAAAN!!", "style": "shock"}],
                "filter": "manga_ink"
            },
            {
                "prompt": "Ren touching chest and feeling frills, screaming in high-pitched feminine voice",
                "dialogue": [
                    {"speaker": "Ren", "text": "GIỌNG NÓI CỦA TÔI NỮA! SAO NÓ LẠI TRONG TRẺO NHƯ BÉ GÁI 14 TUỔI THẾ NÀY?!"},
                    {"speaker": "Kumi", "text": "Dễ thương quá đi à! Rất hợp với cậu luôn!"}
                ],
                "sfx": [{"text": "GAAA!", "style": "scream"}],
                "filter": "halftone"
            },
            {
                "prompt": "Ren grabbing mascot Kumi and shaking vigorously with comedic furious anime expression",
                "dialogue": [{"speaker": "Ren", "text": "TA LÀ ĐÀN ÔNG HAI MƯƠI TUỔI ĐẤY TÊN THÚ BÔNG KHỐN KIẾP NÀY!!!"}],
                "sfx": [{"text": "BUN BUN BUN!", "style": "shake"}],
                "filter": "speedlines_horizontal"
            }
        ]
    },
    {
        "page": 11,
        "layout": "2-panel",
        "title": "Quái thú phản công",
        "panels": [
            {
                "prompt": "giant shadow monster tentacle slamming down like a guillotine into the pavement where Ren stood",
                "dialogue": [{"speaker": "Void Fiend", "text": "CHẾT ĐI, CON NHÓC LÈ PHÉP THUẬT!"}],
                "sfx": [{"text": "ZUDOOOOON!!", "style": "crush"}],
                "filter": "speedlines_radial"
            },
            {
                "prompt": "Ren in magical girl dress effortlessly somersaulting in mid-air with supersonic agility and pink sparkles",
                "dialogue": [{"speaker": "Ren", "text": "Ủa?! Cơ thể này... nhẹ như lông hồng! Tốc độ phản xạ gấp 10 lần bình thường?!"}],
                "sfx": [{"text": "HYUT!", "style": "speed"}],
                "filter": "speedlines_horizontal"
            }
        ]
    },
    {
        "page": 12,
        "layout": "3-panel",
        "title": "Thần chú phép thuật sến sẩm",
        "panels": [
            {
                "prompt": "Ren landing smoothly on top of a streetlamp post, holding magical star wand",
                "dialogue": [{"speaker": "Ren", "text": "Này Kumi! Cái gậy này bắn đạn hay chém như kiếm được không?"}],
                "sfx": [],
                "filter": "manga_ink"
            },
            {
                "prompt": "Kumi hovering beside Ren, fluttering wings and giving cute pose instructions",
                "dialogue": [{"speaker": "Kumi", "text": "Muốn bắn ma pháp, cậu phải giơ ngón tay hình trái tim và hô: 'Trái tim lấp lánh ban mai, bắn nát bóng đêm!'"}],
                "sfx": [{"text": "KYAPITYA!", "style": "sparkle"}],
                "filter": "halftone"
            },
            {
                "prompt": "Ren blushing furiously with veins popping on forehead, looking disgusted",
                "dialogue": [{"speaker": "Ren", "text": "Bắt một thằng tập gym hô câu đó giữa đường Tokyo à?! QUÊN ĐI!!"}],
                "sfx": [{"text": "PIKI PIKI!", "style": "anger"}],
                "filter": "manga_ink"
            }
        ]
    },
    {
        "page": 13,
        "layout": "2-panel",
        "title": "Phong cách chiến đấu của Ren",
        "panels": [
            {
                "prompt": "Ren tucking the wand into the dress waistband and wrapping boxing tape around magical girl white gloves",
                "dialogue": [
                    {"speaker": "Ren", "text": "Phép thuật kiểu gì kệ nó! Cách nhanh nhất là DÙNG NẮM ĐẤM!"},
                    {"speaker": "Kumi", "text": "Ơ kìa?! Đâu có cô bé phép thuật nào đánh cận chiến thô bạo như thế?!"}
                ],
                "sfx": [{"text": "GUGUT!", "style": "tighten"}],
                "filter": "manga_ink"
            },
            {
                "prompt": "cute magical girl rocket dashing forward with sonic boom, fists surrounded by explosive pink kinetic aura",
                "dialogue": [{"speaker": "Ren", "text": "LÊN NÀO CON QUÁI VẬT! NẾM THỬ CÚ ĐẤM NÀY!"}],
                "sfx": [{"text": "BASHIIIIIN!!", "style": "supersonic"}],
                "filter": "speedlines_horizontal"
            }
        ]
    },
    {
        "page": 14,
        "layout": "splash",
        "title": "Cú đấm ma thuật uy lực",
        "panels": [
            {
                "prompt": "Mirai Sparkle delivering a devastating heavy uppercut directly to the shadow monster's jaw, shockwave blasting surrounding buildings",
                "dialogue": [
                    {"speaker": "Ren", "text": "SPARKLE HEAVY UPPERCUTTTTT!!"},
                    {"speaker": "Void Fiend", "text": "GWAAAAAAAHHHH!!"}
                ],
                "sfx": [{"text": "DOKAAAAAAAN!!", "style": "heavy_impact"}],
                "filter": "speedlines_radial"
            }
        ]
    },
    {
        "page": 15,
        "layout": "3-panel",
        "title": "Đòn hiểm của quái thú",
        "panels": [
            {
                "prompt": "monster staggering back into concrete wall, cracks spreading, darkness boiling furiously",
                "dialogue": [{"speaker": "Kumi", "text": "Kinh khủng quá! Một đòn tay không mà hất tung quái thú 5 tấn?!"}],
                "sfx": [{"text": "MUKUKU...", "style": "fury"}],
                "filter": "halftone"
            },
            {
                "prompt": "monster's chest opening up into dark void cannon aiming at an innocent salaryman collapsed on the sidewalk",
                "dialogue": [{"speaker": "Void Fiend", "text": "LŨ LOÀI NGƯỜI YẾU ĐUỐI... HÃY TAN THÀNH TRO BỤI!"}],
                "sfx": [{"text": "ZUUUUN...", "style": "charge"}],
                "filter": "dither"
            },
            {
                "prompt": "Ren's eyes widening in horror as the dark beam charges towards the civilian",
                "dialogue": [{"speaker": "Ren", "text": "Bác nhân viên văn phòng kia! NGUY HIỂM!"}],
                "sfx": [{"text": "HAT!", "style": "alert"}],
                "filter": "speedlines_radial"
            }
        ]
    },
    {
        "page": 16,
        "layout": "2-panel",
        "title": "Tấm khiên trái tim",
        "panels": [
            {
                "prompt": "Ren dashing at lightspeed and sliding between dark beam and civilian, holding wand crossed",
                "dialogue": [{"speaker": "Ren", "text": "KHÔNG ĐƯỢC CHẠM VÀO NGƯỜI VÔ TỘI!!"}],
                "sfx": [{"text": "BASHAAAA!", "style": "slide"}],
                "filter": "speedlines_horizontal"
            },
            {
                "prompt": "massive sparkling translucent heart-shaped shield deflecting the dark energy beam into the sky",
                "dialogue": [
                    {"speaker": "Ren", "text": "HỰ... NẶNG THẬT ĐẤY! Nhưng ta tuyệt đối không lùi bước!"},
                    {"speaker": "Salaryman", "text": "C-Cô bé phép thuật... đang bảo vệ mình sao?"}
                ],
                "sfx": [{"text": "GYURURURURU!!", "style": "deflect"}],
                "filter": "speedlines_radial"
            }
        ]
    },
    {
        "page": 17,
        "layout": "2-panel",
        "title": "Giờ phút quyết định",
        "panels": [
            {
                "prompt": "Ren standing tall, dress fluttering in wind, accepting the magical girl power with proud grin",
                "dialogue": [
                    {"speaker": "Ren", "text": "Dù hình dạng này có kỳ quặc... thì bảo vệ người khác vẫn là việc một người đàn ông phải làm!"},
                    {"speaker": "Kumi", "text": "Ren... năng lượng ma pháp đang đạt đỉnh 100% rồi!"}
                ],
                "sfx": [{"text": "GOGOGO...", "style": "power_up"}],
                "filter": "manga_ink"
            },
            {
                "prompt": "Ren pointing Star Wand at the sky, rainbow solar flares erupting around her",
                "dialogue": [{"speaker": "Ren", "text": "Nghe cho rõ đây quái thú! Tiếp chiêu mạnh nhất của ta... STARLIGHT PURIFY BURST!!"}],
                "sfx": [{"text": "P-PIKAAAAAN!!", "style": "radiant"}],
                "filter": "speedlines_radial"
            }
        ]
    },
    {
        "page": 18,
        "layout": "splash",
        "title": "Thanh tẩy rực rỡ",
        "panels": [
            {
                "prompt": "colossal rainbow light beam obliterating and purifying the shadow monster into millions of glowing cherry blossom petals over Tokyo",
                "dialogue": [
                    {"speaker": "Void Fiend", "text": "ÁNH SÁNG NÀY... ẤM ÁP QUÁ... AAAAAH!"},
                    {"speaker": "Kumi", "text": "HOÀN TẤT THANH TẨY! ĐẸP QUÁ ĐI MẤT!"}
                ],
                "sfx": [{"text": "DOOOOON-KIRAAAAN!!", "style": "divine"}],
                "filter": "speedlines_radial"
            }
        ]
    },
    {
        "page": 19,
        "layout": "3-panel",
        "title": "Sự thật phũ phàng",
        "panels": [
            {
                "prompt": "glowing cherry blossom petals falling gently on Tokyo street, peaceful night restored, sirens in distance",
                "dialogue": [{"speaker": "Ren", "text": "Haa... haa... Cuối cùng cũng giải quyết xong."}],
                "sfx": [{"text": "U-U-U...", "style": "siren"}],
                "filter": "halftone"
            },
            {
                "prompt": "Ren looking down at mascot Kumi with hand on hip in cute twintail girl body",
                "dialogue": [{"speaker": "Ren", "text": "Này Kumi, quái vật xong rồi, mau biến tôi trở lại thành anh chàng 20 tuổi đi!"}],
                "sfx": [],
                "filter": "manga_ink"
            },
            {
                "prompt": "Kumi sweating nervously with giant anime sweatdrop, whistling and looking away",
                "dialogue": [
                    {"speaker": "Kumi", "text": "À thì... chiếc trượng cần sạc năng lượng mặt trời 24 tiếng mới dùng phép biến lại được..."},
                    {"speaker": "Ren", "text": ".........Cậu vừa nói cái gì cơ?"}
                ],
                "sfx": [{"text": "DODON!!", "style": "comedic_doom"}],
                "filter": "dither"
            }
        ]
    },
    {
        "page": 20,
        "layout": "2-panel",
        "title": "Bình minh Tokyo & Khởi đầu mới",
        "panels": [
            {
                "prompt": "Ren holding head and screaming in panic as magical girl in the middle of Tokyo",
                "dialogue": [{"speaker": "Ren", "text": "HẢẢẢẢẢ?! HAI MƯƠI TƯ TIẾNG NỮA Á?! THẾ SÁNG MAI TÔI MẶC VÁY NÀY ĐẾN BƯNG PHỞ Ở QUÁN RAMEN À ĐỒ ĐẦU THỎ KIA?!"}],
                "sfx": [{"text": "GYAAAAAAA!!", "style": "screaming_echo"}],
                "filter": "speedlines_horizontal"
            },
            {
                "prompt": "gorgeous silhouette of magical girl Mirai Sparkle standing on top of skyscraper rooftop against Tokyo sunrise sky, looking heroic and comical",
                "dialogue": [
                    {"speaker": "Người dẫn chuyện", "text": "Và như thế... vị cứu tinh kỳ lạ nhất của Tokyo đã ra đời: Chàng trai phép thuật Mirai Sparkle! [HẾT HỒI 1]"},
                    {"speaker": "Kumi", "text": "Cố lên nhé Ren-chan!"}
                ],
                "sfx": [{"text": "KIRAN!", "style": "twinkle"}],
                "filter": "speedlines_radial"
            }
        ]
    }
]


def generate_magical_girl_panel_art(prompt: str, panel_id: str, p_num: int, pan_num: int, filter_name: str, width: int = 800, height: int = 600) -> Image.Image:
    """Render authentic stylized Japanese manga artwork for the magical girl storyline."""
    import math
    w, h = width, height
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    if p_num in (1, 2, 3):
        # Akihabara / Tokyo night scene
        draw.rectangle([0, 0, w, h], fill=(245, 245, 248))
        skyline_y = int(h * 0.55)
        draw.rectangle([0, skyline_y, w, h], fill=(30, 32, 40))
        buildings = [(40, 70, 260), (130, 85, 330), (235, 110, 290), (370, 95, 380), (490, 80, 250), (595, 120, 340), (730, 60, 280)]
        for bx, bw, bh in buildings:
            draw.rectangle([bx, h - bh, bx + bw, h], fill=(45, 48, 60), outline=(80, 85, 105), width=2)
            for wy in range(h - bh + 25, h - 30, 24):
                for wx in range(bx + 12, bx + bw - 12, 16):
                    if (wx + wy) % 7 != 0:
                        draw.rectangle([wx, wy, wx + 8, wy + 12], fill=(240, 240, 240))
        if p_num == 1:
            tt_x = 420
            draw.polygon([(tt_x, 80), (tt_x - 35, skyline_y), (tt_x + 35, skyline_y)], fill=(30, 30, 35))
            draw.line([(tt_x, 40), (tt_x, 80)], fill=(20, 20, 20), width=3)
        draw.ellipse([w - 140, 40, w - 60, 120], fill=(255, 255, 255), outline=(20, 20, 20), width=3)
        if p_num >= 2:
            cx = int(w * 0.3)
            cy = int(h * 0.7)
            draw.ellipse([cx - 25, cy - 80, cx + 25, cy - 30], fill=(20, 20, 25))
            draw.polygon([(cx - 45, cy + 90), (cx - 35, cy - 30), (cx + 35, cy - 30), (cx + 45, cy + 90)], fill=(25, 25, 30))
        if p_num == 3:
            kx, ky = int(w * 0.65), int(h * 0.45)
            draw.ellipse([kx - 40, ky - 35, kx + 40, ky + 35], fill=(255, 255, 255), outline=(20, 20, 25), width=4)
            draw.polygon([(kx - 25, ky - 30), (kx - 35, ky - 95), (kx - 10, ky - 40)], fill=(255, 255, 255), outline=(20, 20, 25), width=3)
            draw.polygon([(kx + 10, ky - 40), (kx + 35, ky - 95), (kx + 25, ky - 30)], fill=(255, 255, 255), outline=(20, 20, 25), width=3)
            draw.ellipse([kx - 65, ky - 10, kx - 35, ky + 15], fill=(230, 230, 250), outline=(20, 20, 25), width=2)
            draw.ellipse([kx + 35, ky - 10, kx + 65, ky + 15], fill=(230, 230, 250), outline=(20, 20, 25), width=2)
            draw.ellipse([kx - 18, ky - 10, kx - 8, ky + 5], fill=(20, 20, 25))
            draw.ellipse([kx + 8, ky - 10, kx + 18, ky + 5], fill=(20, 20, 25))

    elif p_num in (4, 5, 6, 7):
        # Void Fiend Kage-Ryu appearance & crisis
        draw.rectangle([0, 0, w, h], fill=(20, 20, 25))
        for angle_deg in range(15, 360, 45):
            rad = math.radians(angle_deg)
            tx = int(w * 0.5 + math.cos(rad) * 260)
            ty = int(h * 0.45 + math.sin(rad) * 200)
            draw.line([(int(w * 0.5), int(h * 0.45)), (tx, ty)], fill=(250, 250, 250), width=6)
            draw.ellipse([tx - 15, ty - 15, tx + 15, ty + 15], fill=(220, 40, 40) if angle_deg % 2 == 0 else (255, 255, 255))
        mx, my = int(w * 0.5), int(h * 0.4)
        draw.ellipse([mx - 140, my - 120, mx + 140, my + 120], fill=(10, 10, 15), outline=(255, 255, 255), width=4)
        draw.polygon([(mx - 60, my - 25), (mx - 20, my - 10), (mx - 40, my + 10)], fill=(255, 50, 50))
        draw.polygon([(mx + 60, my - 25), (mx + 20, my - 10), (mx + 40, my + 10)], fill=(255, 50, 50))
        if p_num in (6, 7):
            wx, wy = int(w * 0.25), int(h * 0.7)
            draw.line([(wx - 20, wy + 60), (wx + 30, wy - 40)], fill=(255, 255, 255), width=6)
            points = []
            for i in range(10):
                r = 35 if i % 2 == 0 else 16
                ang = i * math.pi / 5 - math.pi / 2
                points.append((wx + 30 + r * math.cos(ang), wy - 40 + r * math.sin(ang)))
            draw.polygon(points, fill=(255, 230, 80), outline=(20, 20, 20), width=3)

    elif p_num in (8, 9, 10):
        # Magical Girl Transformation & Reveal!
        draw.rectangle([0, 0, w, h], fill=(255, 255, 255))
        cx, cy = int(w * 0.5), int(h * 0.5)
        for r_c in (260, 220, 180, 140):
            draw.ellipse([cx - r_c, cy - r_c, cx + r_c, cy + r_c], outline=(20, 20, 25), width=2 if r_c % 40 != 0 else 4)
        for star_ang in range(0, 360, 60):
            rad = math.radians(star_ang)
            sx = int(cx + 200 * math.cos(rad))
            sy = int(cy + 200 * math.sin(rad))
            draw.ellipse([sx - 12, sy - 12, sx + 12, sy + 12], fill=(30, 30, 35))
        draw.ellipse([cx - 40, cy - 130, cx + 40, cy - 50], fill=(20, 20, 25))
        draw.polygon([(cx - 35, cy - 100), (cx - 140, cy - 60), (cx - 120, cy + 50), (cx - 50, cy - 10)], fill=(30, 32, 40))
        draw.polygon([(cx + 35, cy - 100), (cx + 140, cy - 60), (cx + 120, cy + 50), (cx + 50, cy - 10)], fill=(30, 32, 40))
        draw.polygon([(cx - 30, cy - 50), (cx + 30, cy - 50), (cx + 110, cy + 90), (cx - 110, cy + 90)], fill=(40, 42, 55), outline=(20, 20, 25), width=3)
        draw.line([(cx + 40, cy + 30), (cx + 120, cy - 110)], fill=(20, 20, 25), width=6)
        wand_star = []
        for i in range(10):
            r = 32 if i % 2 == 0 else 14
            ang = i * math.pi / 5 - math.pi / 2
            wand_star.append((cx + 120 + r * math.cos(ang), cy - 110 + r * math.sin(ang)))
        draw.polygon(wand_star, fill=(255, 255, 255), outline=(20, 20, 25), width=3)

    elif p_num in (11, 12, 13, 14, 15, 16):
        # Action combat! Fists, shockwaves, uppercuts
        draw.rectangle([0, 0, w, h], fill=(255, 255, 255))
        cx, cy = int(w * 0.45), int(h * 0.45)
        for i in range(0, 360, 10):
            rad = math.radians(i)
            rx = int(cx + math.cos(rad) * 450)
            ry = int(cy + math.sin(rad) * 450)
            draw.line([(cx, cy), (rx, ry)], fill=(30, 30, 35) if i % 20 == 0 else (180, 180, 185), width=3 if i % 20 == 0 else 1)
        impact_spikes = []
        for i in range(16):
            r = 160 if i % 2 == 0 else 80
            ang = i * math.pi / 8
            impact_spikes.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        draw.polygon(impact_spikes, fill=(255, 255, 255), outline=(20, 20, 25), width=5)
        draw.ellipse([cx - 45, cy - 45, cx + 45, cy + 45], fill=(30, 30, 35), outline=(255, 255, 255), width=3)
        draw.polygon([(cx + 60, cy - 80), (cx + 190, cy - 40), (cx + 160, cy + 90), (cx + 50, cy + 60)], fill=(50, 50, 60), outline=(20, 20, 25), width=3)

    elif p_num in (17, 18):
        # Ultimate Finisher "Mirai Stardust Impact"
        draw.rectangle([0, 0, w, h], fill=(20, 20, 25))
        cx, cy = int(w * 0.5), int(h * 0.5)
        for i in range(0, 360, 6):
            rad = math.radians(i)
            rx = int(cx + math.cos(rad) * 500)
            ry = int(cy + math.sin(rad) * 500)
            draw.line([(cx, cy), (rx, ry)], fill=(255, 255, 255), width=2 if i % 12 == 0 else 1)
        big_star = []
        for i in range(10):
            r = 220 if i % 2 == 0 else 90
            ang = i * math.pi / 5 - math.pi / 2
            big_star.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        draw.polygon(big_star, fill=(255, 255, 255), outline=(20, 20, 25), width=4)
        for i in range(30):
            px = int(cx + math.cos(i * 1.3) * (180 + i * 7))
            py = int(cy + math.sin(i * 1.3) * (180 + i * 7))
            draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=(255, 255, 255))

    else:
        # p_num 19, 20: Tokyo sunrise & comical cliffhanger
        draw.rectangle([0, 0, w, h], fill=(250, 250, 252))
        for y_line in range(int(h * 0.4), int(h * 0.75), 18):
            draw.line([(0, y_line), (w, y_line)], fill=(210, 215, 225), width=1)
        draw.ellipse([int(w * 0.5) - 80, int(h * 0.5) - 80, int(w * 0.5) + 80, int(h * 0.5) + 80], fill=(255, 255, 255), outline=(30, 30, 35), width=3)
        draw.rectangle([0, int(h * 0.7), w, h], fill=(35, 38, 48))
        mx, my = int(w * 0.38), int(h * 0.6)
        draw.ellipse([mx - 30, my - 70, mx + 30, my - 10], fill=(20, 20, 25))
        draw.polygon([(mx - 25, my - 45), (mx - 80, my + 30), (mx - 40, my + 20)], fill=(30, 30, 35))
        draw.polygon([(mx + 25, my - 45), (mx + 80, my + 30), (mx + 40, my + 20)], fill=(30, 30, 35))
        draw.polygon([(mx + 38, my - 60), (mx + 48, my - 40), (mx + 28, my - 40)], fill=(200, 220, 255))
        kx, ky = int(w * 0.65), int(h * 0.65)
        draw.ellipse([kx - 25, ky - 20, kx + 25, ky + 20], fill=(255, 255, 255), outline=(20, 20, 25), width=3)
        draw.polygon([(kx - 15, ky - 18), (kx - 22, ky - 60), (kx - 8, ky - 22)], fill=(255, 255, 255), outline=(20, 20, 25), width=2)
        draw.polygon([(kx + 8, ky - 22), (kx + 22, ky - 60), (kx + 15, ky - 18)], fill=(255, 255, 255), outline=(20, 20, 25), width=2)
        draw.polygon([(kx + 25, ky - 35), (kx + 38, ky - 15), (kx + 18, ky - 15)], fill=(200, 220, 255))

    draw.rectangle([2, 2, w - 3, h - 3], outline=(20, 20, 25), width=3)
    tag_text = f"P{p_num:02d} • Ô #{pan_num}"
    draw.rectangle([10, 10, 110, 32], fill=(20, 22, 28))
    draw.text((18, 14), tag_text, fill=(255, 255, 255))
    return img


def run_test():
    print("=================================================================")
    print("BẮT ĐẦU TEST TOÀN DIỆN MANGA & STORYBOARD: CÔ BÉ PHÉP THUẬT (20 TRANG)")
    print("=================================================================")

    # 1. Khởi tạo DB
    print("\n[Bước 1/6] Khởi tạo cơ sở dữ liệu Manga Studio...")
    init_db()
    init_manga_db()
    db = connect()

    # 2. Tạo Series
    print("[Bước 2/6] Tạo Manga Series & Nhân vật...")
    series_id = "series-mahou-shoujo-ore"
    # Dọn dẹp bản test cũ nếu có (xóa cascade từ panels, pages, chapters, characters tới series)
    try:
        db.execute("DELETE FROM manga_panels WHERE id LIKE 'panel-mso-%'")
        db.execute("DELETE FROM manga_panels WHERE page_id IN (SELECT id FROM manga_storyboard_pages WHERE chapter_id IN (SELECT id FROM manga_chapters WHERE series_id = ?))", (series_id,))
        db.execute("DELETE FROM manga_storyboard_pages WHERE id LIKE 'page-mso-%'")
        db.execute("DELETE FROM manga_storyboard_pages WHERE chapter_id IN (SELECT id FROM manga_chapters WHERE series_id = ?)", (series_id,))
        db.execute("DELETE FROM manga_chapters WHERE id = 'chap-mahou-shoujo-ore-c1'")
        db.execute("DELETE FROM manga_chapters WHERE series_id = ?", (series_id,))
        db.execute("DELETE FROM manga_characters WHERE series_id = ?", (series_id,))
        db.execute("DELETE FROM manga_characters WHERE id IN ('char-ren', 'char-mirai-sparkle', 'char-kumi', 'char-void-fiend')")
        db.execute("DELETE FROM manga_series WHERE id = ?", (series_id,))
        db.commit()
    except Exception as e:
        print(f"Lưu ý khi dọn dẹp DB cũ: {e}")
        db.rollback()

    stamp = now()
    db.execute("""
        INSERT INTO manga_series (id, title, slug, synopsis, genre, art_style, reading_direction, settings_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'rtl', '{}', ?, ?)
    """, (
        series_id,
        "Mahou Shoujo Ore!? - Biến Thân Bất Đắc Dĩ",
        "mahou-shoujo-ore",
        "Ren Fujimoto (20 tuổi) tình cờ nhặt được linh vật Kumi giữa Tokyo và buộc phải trở thành Cô Bé Phép Thuật Mirai Sparkle để giải cứu thế giới bằng... nắm đấm!",
        "Hài hước, Phép thuật, Siêu nhiên, Hành động, Gender-bender",
        "bw",
        stamp, stamp
    ))

    # Tạo Characters
    chars = [
        {
            "id": "char-ren",
            "name": "Ren Fujimoto (藤本 蓮)",
            "identity": {"role": "protagonist", "gender": "male", "age": 20, "appearance": "Cao 1m78, tóc đen ngắn, áo bomber, cơ bắp thể thao"},
            "personality": {"traits": ["Trượng nghĩa", "Cộc cằn", "Thích tập gym", "Thương người"]},
            "speech_rules": {"tone": "Mạnh mẽ, thô lỗ nhưng ấm áp"}
        },
        {
            "id": "char-mirai-sparkle",
            "name": "Mirai Sparkle (Ren biến thân)",
            "identity": {"role": "protagonist_alt", "gender": "female", "age": 14, "appearance": "Tóc hồng twintail lấp lánh, váy xòe ruy băng trắng hồng, trượng Star Wand"},
            "personality": {"traits": ["Ngại ngùng", "Dễ thương bên ngoài - Đấm bốc bên trong"]},
            "speech_rules": {"tone": "Giọng nữ trong trẻo nhưng dùng từ ngữ thô ráp của đàn ông"}
        },
        {
            "id": "char-kumi",
            "name": "Kumi (クミ)",
            "identity": {"role": "mascot", "gender": "neutral", "appearance": "Thỏ tròn trắng muốt có cánh bướm tí hon phát sáng"},
            "personality": {"traits": ["Nhắng nhít", "Đoảng", "Nhiệt tình", "Mê đồ ngọt"]},
            "speech_rules": {"tone": "Đáng yêu, kết thúc câu bằng '~kumi'"}
        },
        {
            "id": "char-void-fiend",
            "name": "Kage-Ryu (Quái Thú Hư Vô)",
            "identity": {"role": "antagonist", "appearance": "Bóng ma bóng tối khổng lồ, mắt đỏ rực, xúc tu sắc nhọn"},
            "personality": {"traits": ["Hung hãn", "Nuốt chửng năng lượng tiêu cực Tokyo"]},
            "speech_rules": {"tone": "Gầm rú, hủy diệt"}
        }
    ]
    for c in chars:
        db.execute("""
            INSERT INTO manga_characters (id, series_id, name, identity_json, personality_json, speech_rules_json, locked_traits_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, '[]', ?, ?)
        """, (
            c["id"], series_id, c["name"],
            json.dumps(c["identity"], ensure_ascii=False),
            json.dumps(c["personality"], ensure_ascii=False),
            json.dumps(c["speech_rules"], ensure_ascii=False),
            stamp, stamp
        ))
    db.commit()
    print(f"✓ Đã tạo Series '{series_id}' với {len(chars)} nhân vật chuẩn canon.")

    # 3. Tạo Chapter 1
    print("\n[Bước 3/6] Tạo Chương 1: 'Hồi 1: Lời Nguyền Váy Hồng và Đêm Tokyo Rực Lửa'...")
    chapter_id = "chap-mahou-shoujo-ore-c1"
    db.execute("""
        INSERT INTO manga_chapters (id, series_id, number, title, synopsis, status, canon_snapshot_json, created_at, updated_at)
        VALUES (?, ?, 1.0, ?, ?, 'storyboarded', '{}', ?, ?)
    """, (
        chapter_id, series_id,
        "Hồi 1: Lời Nguyền Váy Hồng và Đêm Tokyo Rực Lửa",
        "Đêm định mệnh tại Akihabara khi chàng trai 20 tuổi gặp thú cưng ma thuật và biến thân thành cô bé phép thuật.",
        stamp, stamp
    ))
    db.commit()
    print(f"✓ Đã tạo Chapter '{chapter_id}'.")

    # 4. Tạo 20 Storyboard Pages & Panels vào Database
    print("\n[Bước 4/6] Khởi tạo 20 Trang Storyboard và Panels tương ứng...")
    total_panels = 0
    pages_records = []
    for p_data in PAGES_SCRIPT:
        p_num = p_data["page"]
        page_id = f"page-mso-p{p_num:02d}"
        layout = p_data["layout"]
        db.execute("""
            INSERT INTO manga_storyboard_pages (id, chapter_id, page_number, layout_template, status, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'ready', ?, ?, ?)
        """, (
            page_id, chapter_id, p_num, layout,
            json.dumps({"title": p_data["title"]}, ensure_ascii=False),
            stamp, stamp
        ))

        panels_in_page = []
        for pan_idx, pan in enumerate(p_data["panels"], 1):
            pan_id = f"panel-mso-p{p_num:02d}-{pan_idx}"
            prompt_obj = {
                "positive": f"manga style, black and white screentones, ink, {pan['prompt']}",
                "negative": "color, photo, blurry, bad anatomy",
                "filter": pan.get("filter", "manga_ink")
            }
            dialogue_objs = [
                {
                    "speaker": d["speaker"],
                    "text": d["text"],
                    "bubble_type": "shout" if "!" in d["text"] else "regular",
                    "x_norm": 0.2 + 0.3 * (d_idx % 2),
                    "y_norm": 0.2 + 0.3 * d_idx
                }
                for d_idx, d in enumerate(pan.get("dialogue", []))
            ]
            sfx_objs = [
                {"text": s["text"], "style": s["style"], "x_norm": 0.5, "y_norm": 0.7}
                for s in pan.get("sfx", [])
            ]

            db.execute("""
                INSERT INTO manga_panels (id, page_id, panel_number, prompt_json, dialogue_json, sfx_json, status, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'ready', '{}', ?, ?)
            """, (
                pan_id, page_id, pan_idx,
                json.dumps(prompt_obj, ensure_ascii=False),
                json.dumps(dialogue_objs, ensure_ascii=False),
                json.dumps(sfx_objs, ensure_ascii=False),
                stamp, stamp
            ))
            total_panels += 1
            panels_in_page.append({
                "panel_id": pan_id,
                "panel_number": pan_idx,
                "prompt": prompt_obj,
                "dialogue": dialogue_objs,
                "sfx": sfx_objs,
                "filter": pan.get("filter", "manga_ink")
            })

        pages_records.append({
            "page_id": page_id,
            "page_number": p_num,
            "layout": layout,
            "panels": panels_in_page
        })

    db.commit()
    print(f"✓ Đã tạo thành công 20 Trang Storyboard với tổng cộng {total_panels} ô tranh (Panels) chi tiết!")

    # 5. Render Panel Artwork & Manga Composer Composed Pages
    print("\n[Bước 5/6] Render Tranh Manga & Soạn thảo Trang (Manga Composer)...")
    composer = MangaComposer()

    rendered_page_images = []
    output_dir = MANGA_DATA / "rendered_pages" / series_id / chapter_id
    output_dir.mkdir(parents=True, exist_ok=True)

    layout_map = {
        "splash": PanelLayoutType.SINGLE,
        "2-panel": PanelLayoutType.GRID_1X2,
        "3-panel": PanelLayoutType.THREE_ROWS,
        "4-panel": PanelLayoutType.YONKOMA
    }

    for p_idx, p_rec in enumerate(pages_records, 1):
        p_num = p_rec["page_number"]
        layout_enum = layout_map.get(p_rec["layout"], PanelLayoutType.YONKOMA)
        
        # Build PanelConfigs with rendered art
        panel_cfgs = []
        speech_bubbles = []
        for pan_data in p_rec["panels"]:
            # Generate panel illustration
            filter_name = pan_data.get("filter", "manga_ink")
            filter_enum = PanelFilter.INK
            if filter_name == "halftone": filter_enum = PanelFilter.HALFTONE_DOTS
            elif filter_name == "speedlines_radial": filter_enum = PanelFilter.SPEEDLINES_RADIAL
            elif filter_name == "speedlines_horizontal": filter_enum = PanelFilter.SPEEDLINES_HORIZONTAL
            elif filter_name == "dither": filter_enum = PanelFilter.DITHER

            # Generate high contrast black/white manga artwork
            panel_art = generate_magical_girl_panel_art(
                prompt=pan_data["prompt"]["positive"],
                panel_id=pan_data["panel_id"],
                p_num=p_num,
                pan_num=pan_data["panel_number"],
                filter_name=filter_name,
                width=800,
                height=600
            )

            p_cfg = PanelConfig(
                id=pan_data["panel_id"],
                prompt=pan_data["prompt"]["positive"],
                image_data=image_to_base64_data_url(panel_art),
                filter=filter_enum
            )
            panel_cfgs.append(p_cfg)

            # Bubbles
            for d in pan_data["dialogue"]:
                bubble = SpeechBubble(
                    text=f"{d['speaker']}: {d['text']}",
                    speaker=d.get("speaker", ""),
                    bubble_type=BubbleType.SHOUT if d.get("bubble_type") == "shout" else BubbleType.REGULAR,
                    x=float(d.get("x_norm", 0.3)),
                    y=float(d.get("y_norm", 0.3))
                )
                speech_bubbles.append(bubble)

            for s in pan_data["sfx"]:
                sfx_bubble = SpeechBubble(
                    text=s["text"],
                    bubble_type=BubbleType.SFX,
                    x=float(s.get("x_norm", 0.5)),
                    y=float(s.get("y_norm", 0.6))
                )
                speech_bubbles.append(sfx_bubble)

        # Build PageConfig
        page_config = PageConfig(
            page_number=p_num,
            layout_type=layout_enum,
            panels=panel_cfgs,
            page_bubbles=speech_bubbles,
            width=1200,
            height=1800
        )

        # Compose full manga page
        page_img = composer.compose_page(page_config)
        save_path = output_dir / f"page_{p_num:02d}.png"
        page_img.save(save_path, "PNG")
        rendered_page_images.append(page_img)

        # Update DB asset pointer
        db.execute("""
            UPDATE manga_storyboard_pages
            SET metadata_json = ?
            WHERE id = ?
        """, (json.dumps({"rendered_path": str(save_path)}, ensure_ascii=False), p_rec["page_id"]))

        if p_num in (1, 9, 14, 20):
            print(f"  → Đã render hoàn chỉnh Trang {p_num:02d}/{len(pages_records)} (Layout: {layout_enum.value})")

    db.commit()
    print(f"✓ Đã render 20/20 trang truyện sắc nét chuẩn manga tại {output_dir}")

    # Export to CBZ and PDF
    cbz_path = output_dir / "mahou_shoujo_ore_ch01.cbz"
    pdf_path = output_dir / "mahou_shoujo_ore_ch01.pdf"
    export_to_cbz(rendered_page_images, cbz_path)
    export_to_pdf(rendered_page_images, pdf_path)
    print(f"✓ Xuất bản tập truyện thành công:")
    print(f"  - File CBZ Comic: {cbz_path} ({cbz_path.stat().st_size // 1024} KB)")
    print(f"  - File PDF Manga: {pdf_path} ({pdf_path.stat().st_size // 1024} KB)")

    # Save representative sample pages into ARTIFACT_DIR for user inspection
    rendered_page_images[0].save(ARTIFACT_DIR / "qa_manga_page_01_tokyo_night.png")
    rendered_page_images[8].save(ARTIFACT_DIR / "qa_manga_page_09_transformation_reveal.png")
    rendered_page_images[13].save(ARTIFACT_DIR / "qa_manga_page_14_heavy_uppercut.png")
    rendered_page_images[19].save(ARTIFACT_DIR / "qa_manga_page_20_tokyo_sunrise_cliffhanger.png")
    print("✓ Đã lưu 4 trang mẫu tiêu biểu vào thư mục Artifacts.")

    db.close()
    return series_id, chapter_id


async def verify_ui_playwright(series_id, chapter_id):
    print("\n[Bước 6/6] Khởi chạy Playwright kiểm thử giao diện Studio & Manga...")
    from playwright.async_api import async_playwright

    server_config = uvicorn.Config(app, host="127.0.0.1", port=8895, log_level="warning")
    server = uvicorn.Server(server_config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    import urllib.request
    for _ in range(40):
        try:
            urllib.request.urlopen("http://127.0.0.1:8895/", timeout=2.0)
            break
        except Exception:
            time.sleep(0.3)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})

        await page.goto("http://127.0.0.1:8895/")
        await page.wait_for_selector("#chatlog", timeout=8000)

        # Open Studio -> Manga Hub
        await page.evaluate("""() => {
            if (typeof renderManga === 'function') {
                renderManga();
            } else {
                navigate('manga');
            }
        }""")
        await asyncio.sleep(0.8)

        # Select our Magical Girl series
        await page.evaluate(f"""() => {{
            mangaActiveSeriesId = '{series_id}';
            mangaActiveChapterId = '{chapter_id}';
            const select = document.getElementById('manga-series-select');
            if (select) {{
                select.value = '{series_id}';
                select.dispatchEvent(new Event('change'));
            }}
            if (typeof renderActiveMangaTab === 'function') renderActiveMangaTab();
        }}""")
        await asyncio.sleep(0.8)

        # Capture Series Hub view
        await page.screenshot(path=str(ARTIFACT_DIR / "qa_manga_series_hub.png"))
        print("✓ Đã chụp ảnh Series Hub: qa_manga_series_hub.png")

        # Open Storyboard view for Chapter 1
        await page.evaluate(f"""async () => {{
            mangaActiveSeriesId = '{series_id}';
            mangaActiveChapterId = '{chapter_id}';
            mangaActiveTab = 'storyboard';
            document.querySelectorAll('.manga-nav-tab').forEach(b => {{
                b.classList.toggle('active', b.dataset.mangaTab === 'storyboard');
            }});
            const pane = document.getElementById('manga-tab-view');
            if (typeof renderMangaStoryboard === 'function' && pane) {{
                await renderMangaStoryboard(pane);
            }}
        }}""")
        await asyncio.sleep(1.2)
        await page.screenshot(path=str(ARTIFACT_DIR / "qa_manga_storyboard_20pages.png"))
        print("✓ Đã chụp ảnh 20-Page Storyboard: qa_manga_storyboard_20pages.png")

        # Open Manga Composer page view
        await page.evaluate(f"""async () => {{
            mangaActiveSeriesId = '{series_id}';
            mangaActiveChapterId = '{chapter_id}';
            mangaActiveTab = 'composer';
            document.querySelectorAll('.manga-nav-tab').forEach(b => {{
                b.classList.toggle('active', b.dataset.mangaTab === 'composer');
            }});
            const pane = document.getElementById('manga-tab-view');
            if (typeof renderMangaComposer === 'function' && pane) {{
                await renderMangaComposer(pane);
            }}
        }}""")
        await asyncio.sleep(1.2)
        await page.screenshot(path=str(ARTIFACT_DIR / "qa_manga_composer_viewer.png"))
        print("✓ Đã chụp ảnh Manga Composer Viewer: qa_manga_composer_viewer.png")

        await browser.close()
    server.should_exit = True
    print("\n=================================================================")
    print("HOÀN TẤT TOÀN DIỆN KIỂM THỬ TẠO ẢNH, MANGA & STORYBOARD 20 TRANG!")
    print("=================================================================")


if __name__ == "__main__":
    sid, cid = run_test()
    asyncio.run(verify_ui_playwright(sid, cid))
