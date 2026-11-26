#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Synthetic Reasoning CoT Dataset Generator
=========================================
Generates standardized Chain-of-Thought (CoT) reasoning training data with explicit
`<think> step-by-step reasoning </think>` blocks, solving classic cognitive traps:
  1. Exponential Lily Pad Growth (with 1, 2, 4, 8, 16, 32 cluster variations, fraction of lake, doubling/tripling/quadrupling)
  2. Character Decomposition Counting (letter-by-letter indexing to resolve tokenization bias like 'strawberry')
  3. Knights and Knaves Truth/Liar Logic Puzzles (rigorous proof by contradiction)
  4. Classic Cognitive & Math Traps (Bat and Ball, Machine Rates, Snail climbing well, Harmonic Mean average speed, Palindromes)

Output format conforms to ChatML / Qwen / HuggingFace TRL / Unsloth format:
  {"id": "...", "category": "...", "messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}], "text": "..."}
"""

import os
import sys
import json
import math
import random
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

SYSTEM_PROMPT_VI = (
    "Bạn là một trợ lý AI có khả năng suy luận logic chuyên sâu. Khi giải quyết bài toán, "
    "hãy luôn phân tích và suy luận từng bước một cách cẩn thận trong thẻ <think> ... </think>, "
    "chỉ ra các bẫy tư duy trực giác nếu có, trước khi đưa ra kết luận chính xác, ngắn gọn và rõ ràng."
)

SYSTEM_PROMPT_EN = (
    "You are an expert AI reasoning assistant. When presented with a problem, break it down "
    "rigorously step-by-step inside <think> ... </think> tags, actively identifying and disproving "
    "common intuitive traps before providing your definitive, clear final answer."
)


# ==============================================================================
# 1. EXPONENTIAL GROWTH & LILY PAD GENERATOR
# ==============================================================================
class LilypadExponentialGenerator:
    """Generates problems modeling exponential growth, refuting linear fallacies."""

    LAKE_NAMES_VI = ["hồ Tây", "hồ Gươm", "hồ sen làng", "ao cá", "hồ sinh thái", "đầm lầy thủy sinh", "hồ nhân tạo", "hồ Ba Bể"]
    ORGANISM_NAMES_VI = ["hoa bèo lục bình", "cụm bèo tấm", "cụm hoa sen", "loài tảo lam", "khóm bèo cái", "thảm rong đuôi chồn"]

    def __init__(self, rng: random.Random):
        self.rng = rng

    def generate(self) -> Dict[str, Any]:
        scenario = self.rng.choice([
            "varied_initial_clusters",
            "fraction_of_lake",
            "initial_clusters_and_fraction",
            "different_growth_rates",
            "bacteria_culture_time",
            "comparative_ponds"
        ])
        if scenario == "varied_initial_clusters":
            return self._gen_varied_initial_clusters()
        elif scenario == "fraction_of_lake":
            return self._gen_fraction_of_lake()
        elif scenario == "initial_clusters_and_fraction":
            return self._gen_initial_clusters_and_fraction()
        elif scenario == "different_growth_rates":
            return self._gen_different_growth_rates()
        elif scenario == "bacteria_culture_time":
            return self._gen_bacteria_culture_time()
        else:
            return self._gen_comparative_ponds()

    def _gen_varied_initial_clusters(self) -> Dict[str, Any]:
        """Starting with K = 2^m clusters (e.g. 2, 4, 8, 16, 32)."""
        m = self.rng.choice([1, 2, 3, 4, 5])
        k = 2 ** m
        total_days = self.rng.choice([20, 24, 28, 30, 32, 36, 40, 45, 48, 50, 60])
        days_needed = total_days - m
        lake = self.rng.choice(self.LAKE_NAMES_VI)
        organism = self.rng.choice(self.ORGANISM_NAMES_VI)
        linear_trap = total_days // k if (total_days // k > 0) else round(total_days / k, 1)

        question = (
            f"Một {organism} trên {lake} có đặc tính sinh trưởng nhân đôi diện tích sau mỗi ngày. "
            f"Nếu ban đầu chỉ thả 1 cụm bèo thì sau đúng {total_days} ngày bèo sẽ phủ kín toàn bộ mặt hồ.\n"
            f"Hỏi nếu ngay từ ban đầu ta thả {k} cụm bèo cùng loại (mỗi cụm phát triển độc lập với cùng tốc độ nhân đôi mỗi ngày) "
            f"thì sau bao nhiêu ngày bèo sẽ phủ kín toàn bộ mặt hồ?"
        )

        think = (
            f"<think>\n"
            f"1. Phân tích đề bài:\n"
            f"- Đối tượng: {organism} tăng trưởng trên {lake}.\n"
            f"- Quy luật tăng trưởng: Diện tích nhân đôi sau mỗi ngày (hệ số tăng trưởng r = 2, tăng theo cấp số nhân).\n"
            f"- Điều kiện gốc: 1 cụm bèo ban đầu mất {total_days} ngày để phủ kín mặt hồ (diện tích S).\n"
            f"- Câu hỏi: Nếu thả {k} cụm bèo ban đầu, cần bao nhiêu ngày để phủ kín mặt hồ?\n\n"
            f"2. Nhận diện bẫy tư duy trực giác (Linear Fallacy):\n"
            f"- Bẫy sai lầm phổ biến: Người giải thường áp dụng tư duy tuyến tính, nghĩ rằng số lượng bèo ban đầu gấp {k} lần thì thời gian sẽ giảm đi {k} lần, tức là lấy {total_days} : {k} = {linear_trap} ngày.\n"
            f"- Lý do sai: Tăng trưởng ở đây là hàm mũ (cấp số nhân), không phải hàm tuyến tính cộng dồn.\n\n"
            f"3. Thiết lập phương trình toán học:\n"
            f"- Gọi diện tích ban đầu của 1 cụm bèo là S_0.\n"
            f"- Sau t ngày, diện tích của 1 cụm bèo là: S(t) = S_0 * 2^t.\n"
            f"- Khi thả 1 cụm, sau {total_days} ngày bèo phủ kín hồ (diện tích S_lake): S_lake = S_0 * 2^{total_days}.\n"
            f"- Khi thả {k} cụm bèo ban đầu ({k} = 2^{m}), tổng diện tích sau t ngày là:\n"
            f"  S_total(t) = {k} * S_0 * 2^t = (2^{m} * S_0) * 2^t = S_0 * 2^{{m + t}}.\n"
            f"- Để bèo phủ kín mặt hồ, ta cần S_total(t) = S_lake:\n"
            f"  S_0 * 2^{{m + t}} = S_0 * 2^{total_days}\n"
            f"  <=> m + t = {total_days}\n"
            f"  <=> {m} + t = {total_days}\n"
            f"  <=> t = {total_days} - {m} = {days_needed} (ngày).\n\n"
            f"4. Kiểm tra lại theo các mốc thời gian:\n"
            f"- Ban đầu (ngày 0), {k} cụm bèo tương đương với lượng bèo mà 1 cụm phát triển sau {m} ngày.\n"
            f"- Vì vậy, quá trình sinh trưởng được 'đi tắt' đúng {m} ngày so với trường hợp 1 cụm.\n"
            f"- Vào ngày {days_needed - 1}: Diện tích đạt 1/2 mặt hồ.\n"
            f"- Vào ngày {days_needed}: Diện tích nhân đôi, đạt chính xác 100% diện tích mặt hồ.\n"
            f"- Mọi phép suy luận hoàn toàn nhất quán và chính xác.\n"
            f"</think>"
        )

        answer = (
            f"Nếu ban đầu thả **{k} cụm bèo**, bèo sẽ phủ kín toàn bộ mặt hồ sau **{days_needed} ngày**.\n\n"
            f"*(Giải thích tóm tắt: Vì {k} = 2^{m}, nên {k} cụm bèo ban đầu tương đương với lượng bèo của 1 cụm đã phát triển qua {m} ngày. "
            f"Do đó, thời gian để phủ kín hồ được rút ngắn đi {m} ngày: {total_days} - {m} = {days_needed} ngày; "
            f"không phải lấy {total_days} chia {k} theo trực giác tuyến tính).* "
        )

        return {
            "category": "exponential_growth_lilypad",
            "difficulty": "medium",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_fraction_of_lake(self) -> Dict[str, Any]:
        """Fraction of lake: 1/2, 1/4, 1/8, 1/16."""
        pow_val = self.rng.choice([1, 2, 3, 4])
        denominator = 2 ** pow_val
        fraction_str = f"1/{denominator}"
        total_days = self.rng.choice([24, 28, 30, 32, 40, 48, 50])
        target_day = total_days - pow_val
        lake = self.rng.choice(self.LAKE_NAMES_VI)
        organism = self.rng.choice(self.ORGANISM_NAMES_VI)
        linear_trap = total_days // denominator

        question = (
            f"Một cụm {organism} trên {lake} nở nhân đôi diện tích mỗi ngày. "
            f"Biết rằng sau đúng {total_days} ngày thì bèo phủ kín toàn bộ mặt hồ. "
            f"Hỏi sau bao nhiêu ngày thì bèo phủ kín {fraction_str} mặt hồ?"
        )

        think = (
            f"<think>\n"
            f"1. Phân tích bài toán:\n"
            f"- Tốc độ sinh trưởng: Diện tích gấp đôi sau mỗi ngày (cấp số nhân, r = 2).\n"
            f"- Ngày {total_days}: Phủ kín 100% (toàn bộ diện tích S của hồ).\n"
            f"- Yêu cầu: Xác định số ngày để bèo phủ {fraction_str} diện tích mặt hồ.\n\n"
            f"2. Bẫy tư duy trực giác (Linear Fallacy):\n"
            f"- Nhiều người thường chia tỉ lệ thuận: lấy {total_days} chia cho {denominator} để ra {linear_trap} ngày. "
            f"Đây là ngụy biện tư duy tuyến tính, hoàn toàn sai lầm đối với hiện tượng tăng trưởng hàm mũ.\n\n"
            f"3. Lập luận suy diễn ngược (Backward Induction):\n"
            f"- Vì mỗi ngày bèo tăng gấp đôi, nên ngày hôm trước diện tích bèo chỉ bằng một nửa (1/2) ngày hôm sau:\n"
            f"  + Ngày {total_days}: Phủ 1 mặt hồ.\n"
            f"  + Ngày {total_days - 1}: Phủ 1/2 mặt hồ.\n"
        )
        if pow_val >= 2:
            think += f"  + Ngày {total_days - 2}: Phủ 1/4 mặt hồ.\n"
        if pow_val >= 3:
            think += f"  + Ngày {total_days - 3}: Phủ 1/8 mặt hồ.\n"
        if pow_val >= 4:
            think += f"  + Ngày {total_days - 4}: Phủ 1/16 mặt hồ.\n"

        think += (
            f"\n4. Công thức toán học:\n"
            f"- S(t) = S_0 * 2^t.\n"
            f"- S({total_days}) = S_lake.\n"
            f"- S(t) = S_lake / {denominator} = S_lake / 2^{pow_val} = S_0 * 2^{{{total_days} - {pow_val}}} = S_0 * 2^{target_day}.\n"
            f"=> t = {total_days} - {pow_val} = {target_day} ngày.\n"
            f"- Kết quả suy luận vững chắc và không có sai số.\n"
            f"</think>"
        )

        answer = (
            f"Bèo sẽ phủ kín **{fraction_str} mặt hồ** sau **{target_day} ngày**.\n\n"
            f"*(Bởi vì diện tích nhân đôi sau mỗi ngày, nên nếu ngày {total_days} đầy hồ thì ngày {total_days - 1} đầy 1/2 hồ, "
            f"ngày {target_day} sẽ đạt {fraction_str} hồ; tuyệt đối không lấy {total_days} chia {denominator}).*"
        )

        return {
            "category": "exponential_growth_lilypad",
            "difficulty": "easy",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_initial_clusters_and_fraction(self) -> Dict[str, Any]:
        """Compound: starting with K clusters, reaches fraction F."""
        init_m = self.rng.choice([1, 2, 3])
        init_k = 2 ** init_m  # 2, 4, 8
        pow_val = self.rng.choice([1, 2])
        denominator = 2 ** pow_val  # 2, 4
        fraction_str = f"1/{denominator}"

        days_for_k = self.rng.choice([20, 24, 28, 30, 36])
        target_day = days_for_k - pow_val
        organism = self.rng.choice(self.ORGANISM_NAMES_VI)
        lake = self.rng.choice(self.LAKE_NAMES_VI)

        question = (
            f"Người ta thả {init_k} cụm {organism} vào {lake}. Biết bèo phát triển nhân đôi diện tích mỗi ngày, "
            f"và sau đúng {days_for_k} ngày thì {init_k} cụm bèo này phủ kín toàn bộ mặt hồ.\n"
            f"Hỏi cũng với {init_k} cụm bèo ban đầu đó, sau bao nhiêu ngày bèo sẽ phủ kín {fraction_str} mặt hồ?"
        )

        think = (
            f"<think>\n"
            f"1. Xác định giả thiết đề bài:\n"
            f"- Điều kiện ban đầu: Có {init_k} cụm bèo.\n"
            f"- Tốc độ sinh trưởng: Nhân đôi mỗi ngày (r = 2).\n"
            f"- Thời gian phủ kín 100% mặt hồ: {days_for_k} ngày.\n"
            f"- Yêu cầu: Tìm thời gian để bèo phủ kín {fraction_str} mặt hồ.\n\n"
            f"2. Bẫy tư duy:\n"
            f"- Chú ý bẫy: Một số người bị phân tâm bởi con số '{init_k} cụm bèo' và cố gắng tính diện tích ban đầu của 1 cụm. "
            f"Tuy nhiên, toàn bộ {init_k} cụm bèo này đóng vai trò như một tập hợp duy nhất khởi đầu tại ngày 0.\n"
            f"- Bẫy khác: Lấy {days_for_k} chia {denominator}.\n\n"
            f"3. Lập luận suy diễn:\n"
            f"- Tập hợp {init_k} cụm bèo đạt 100% diện tích hồ vào ngày {days_for_k}.\n"
            f"- Do mỗi ngày diện tích tăng gấp 2 lần, nên lùi lại từng ngày:\n"
            f"  + Vào ngày {days_for_k - 1}: Diện tích bèo bằng 1/2 mặt hồ.\n"
        )
        if pow_val == 2:
            think += f"  + Vào ngày {days_for_k - 2}: Diện tích bèo bằng 1/4 mặt hồ.\n"

        think += (
            f"- Như vậy, thời điểm đạt {fraction_str} mặt hồ là ngày {target_day}.\n"
            f"- Đáp số này độc lập với việc có bao nhiêu cụm ban đầu, miễn là thời điểm đầy hồ của hệ thống đó là {days_for_k} ngày.\n"
            f"</think>"
        )

        answer = (
            f"Với {init_k} cụm bèo ban đầu, sau **{target_day} ngày** bèo sẽ phủ kín **{fraction_str} mặt hồ**.\n\n"
            f"*(Giải thích: Tại ngày {days_for_k} hồ đầy 100%. Lùi lại mỗi ngày diện tích giảm đi một nửa, "
            f"nên ngày {days_for_k - 1} đạt 1/2 hồ, và ngày {target_day} đạt {fraction_str} hồ).* "
        )

        return {
            "category": "exponential_growth_lilypad",
            "difficulty": "medium",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_different_growth_rates(self) -> Dict[str, Any]:
        """Growth rate r = 3 (tripling) or r = 4 (quadrupling)."""
        rate = self.rng.choice([3, 4])
        m = self.rng.choice([1, 2])
        k = rate ** m  # 3 or 9 for rate=3; 4 or 16 for rate=4
        rate_word = "gấp 3 lần" if rate == 3 else "gấp 4 lần"
        total_days = self.rng.choice([18, 21, 24, 27, 30])
        days_needed = total_days - m

        question = (
            f"Một loại vi tảo đặc biệt trong hồ sinh học có tốc độ tăng trưởng sinh khối {rate_word} sau mỗi 24 giờ. "
            f"Nếu ban đầu có 1 mẫu tảo thì sau đúng {total_days} ngày tảo sẽ bao phủ toàn bộ mặt hồ.\n"
            f"Nếu ngay từ đầu người ta cấy {k} mẫu tảo cùng loại phân bố đều trong hồ (mỗi mẫu phát triển độc lập với tốc độ {rate_word} mỗi ngày) "
            f"thì sau bao nhiêu ngày hồ sẽ bị tảo bao phủ hoàn toàn?"
        )

        think = (
            f"<think>\n"
            f"1. Phân tích bài toán:\n"
            f"- Sinh vật: Vi tảo với tốc độ tăng trưởng r = {rate} sau mỗi ngày (cấp số nhân cơ số {rate}).\n"
            f"- Điều kiện gốc: 1 mẫu tảo phủ kín hồ sau {total_days} ngày => S_lake = S_0 * {rate}^{total_days}.\n"
            f"- Điều kiện mới: Bắt đầu với {k} mẫu tảo ({k} = {rate}^{m}).\n"
            f"- Yêu cầu: Tìm số ngày t để {k} mẫu tảo phủ kín S_lake.\n\n"
            f"2. Nhận diện bẫy tư duy:\n"
            f"- Không được lấy {total_days} chia {k}. Tăng trưởng không diễn ra theo tỉ lệ tuyến tính.\n\n"
            f"3. Giải tích:\n"
            f"- Tổng diện tích sau t ngày: S_total(t) = {k} * S_0 * {rate}^t = {rate}^{m} * S_0 * {rate}^t = S_0 * {rate}^{{m + t}}.\n"
            f"- Để phủ kín hồ: S_0 * {rate}^{{m + t}} = S_0 * {rate}^{total_days}\n"
            f"  <=> m + t = {total_days} <=> {m} + t = {total_days} <=> t = {total_days} - {m} = {days_needed} (ngày).\n"
            f"- Như vậy, việc bắt đầu với {k} mẫu tảo tương đương với việc tiết kiệm được đúng {m} ngày đầu tiên.\n"
            f"</think>"
        )

        answer = (
            f"Sau **{days_needed} ngày**, hồ sẽ bị tảo bao phủ hoàn toàn.\n\n"
            f"*(Vì {k} = {rate}^{m}, nên {k} mẫu tảo ban đầu giúp rút ngắn thời gian sinh trưởng đi đúng {m} ngày: "
            f"{total_days} - {m} = {days_needed} ngày).* "
        )

        return {
            "category": "exponential_growth_lilypad",
            "difficulty": "medium",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_bacteria_culture_time(self) -> Dict[str, Any]:
        """Bacteria dividing every T minutes, English or Vietnamese."""
        cycle_min = self.rng.choice([15, 20, 30])
        total_hours = self.rng.choice([3, 4, 5, 6])
        start_hour = 8
        end_hour = start_hour + total_hours
        question_type = self.rng.choice(["half_full", "start_with_two"])

        if question_type == "half_full":
            sub_min = cycle_min
            end_min = 60 - sub_min
            result_hour = end_hour - 1
            question = (
                f"Một tế bào vi khuẩn trong đĩa nuôi cấy phân đôi sau mỗi {cycle_min} phút. "
                f"Bắt đầu thí nghiệm lúc {start_hour}:00 sáng với 1 tế bào duy nhất, đĩa nuôi cấy chứa đầy vi khuẩn vào đúng {end_hour}:00 trưa. "
                f"Hỏi vào thời điểm nào thì đĩa nuôi cấy chứa đúng một nửa (1/2) lượng vi khuẩn?"
            )
            think = (
                f"<think>\n"
                f"1. Phân tích hiện tượng:\n"
                f"- Tốc độ phân chia: Số lượng tế bào vi khuẩn nhân đôi sau mỗi chu kỳ {cycle_min} phút.\n"
                f"- Trạng thái đầy đĩa: Đạt được vào lúc {end_hour}:00.\n"
                f"- Yêu cầu: Xác định thời điểm lượng vi khuẩn đạt 1/2 đĩa nuôi cấy.\n\n"
                f"2. Bẫy tư duy trực giác:\n"
                f"- Bẫy: Chia đôi tổng thời gian ({total_hours} tiếng = {total_hours * 60} phút / 2 = {total_hours * 30} phút) "
                f"để suy ra thời điểm là {start_hour + total_hours // 2}:00. Đây là sai lầm nghiêm trọng do áp đặt tư duy tuyến tính.\n\n"
                f"3. Lập luận nghịch đảo (Backward reasoning):\n"
                f"- Vì số lượng vi khuẩn nhân đôi sau mỗi {cycle_min} phút, nên trước thời điểm đầy đĩa đúng 1 chu kỳ ({cycle_min} phút), "
                f"số lượng vi khuẩn phải bằng đúng 1/2 đĩa.\n"
                f"- Thời điểm đầy đĩa: {end_hour}:00.\n"
                f"- Thời điểm nửa đĩa = {end_hour}:00 trừ đi {cycle_min} phút = {result_hour}:{end_min:02d}.\n"
                f"</think>"
            )
            answer = (
                f"Đĩa nuôi cấy chứa đúng một nửa (1/2) lượng vi khuẩn vào lúc **{result_hour}:{end_min:02d}** "
                f"(chính xác là {cycle_min} phút trước khi đầy đĩa lúc {end_hour}:00)."
            )
        else:
            # Start with 2 or 4 bacteria
            m = self.rng.choice([1, 2])
            k = 2 ** m
            sub_minutes = m * cycle_min
            sub_h = sub_minutes // 60
            sub_m = sub_minutes % 60
            final_h = end_hour - (1 if sub_m > 0 else sub_h)
            final_m = (60 - sub_m) if sub_m > 0 else 0
            time_str = f"{final_h}:{final_m:02d}"

            question = (
                f"Một mẫu vi khuẩn phân chia nhân đôi số lượng sau mỗi {cycle_min} phút. "
                f"Nếu bắt đầu với 1 tế bào lúc {start_hour}:00 sáng thì ống nghiệm chứa đầy vi khuẩn vào lúc {end_hour}:00 trưa. "
                f"Hỏi nếu bắt đầu với {k} tế bào vi khuẩn lúc {start_hour}:00 sáng thì ống nghiệm sẽ đầy vào lúc mấy giờ?"
            )
            think = (
                f"<think>\n"
                f"1. Xác định bài toán:\n"
                f"- Chu kỳ nhân đôi: {cycle_min} phút.\n"
                f"- Bắt đầu với 1 tế bào lúc {start_hour}:00, đầy lúc {end_hour}:00 (tổng thời gian = {total_hours * 60} phút).\n"
                f"- Bắt đầu với {k} tế bào ({k} = 2^{m} tế bào) lúc {start_hour}:00.\n\n"
                f"2. Bẫy tư duy:\n"
                f"- Không lấy tổng thời gian chia cho {k}.\n\n"
                f"3. Suy luận:\n"
                f"- 1 tế bào sau {m} chu kỳ ({m * cycle_min} phút) sẽ phân chia thành 2^{m} = {k} tế bào.\n"
                f"- Do đó, việc bắt đầu ngay với {k} tế bào tiết kiệm được {m} chu kỳ, tức là {m * cycle_min} phút.\n"
                f"- Thời điểm ống nghiệm đầy: {end_hour}:00 trừ đi {m * cycle_min} phút = {time_str}.\n"
                f"</think>"
            )
            answer = (
                f"Ống nghiệm sẽ chứa đầy vi khuẩn vào lúc **{time_str}** "
                f"(sớm hơn {m * cycle_min} phút so với khi bắt đầu bằng 1 tế bào)."
            )

        return {
            "category": "exponential_growth_lilypad",
            "difficulty": "medium",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_comparative_ponds(self) -> Dict[str, Any]:
        """Comparative question between two ponds or cluster setups."""
        m = self.rng.choice([2, 3, 4])  # 4, 8, 16 clusters
        k = 2 ** m
        days_A = self.rng.choice([26, 30, 32, 40])
        days_B = days_A - m

        question = (
            f"Hai hồ nước A và B có diện tích hoàn toàn bằng nhau. Ở hồ A người ta thả 1 cụm bèo hoa dâu, "
            f"còn ở hồ B người ta thả {k} cụm bèo cùng loại. Biết rằng mỗi cụm bèo ở cả hai hồ đều phát triển "
            f"độc lập và nhân đôi diện tích sau mỗi ngày. Sau đúng {days_A} ngày thì hồ A được phủ kín hoàn toàn.\n"
            f"Hỏi: Hồ B sẽ phủ kín trước hồ A bao nhiêu ngày, và mất bao nhiêu ngày để hồ B phủ kín?"
        )

        think = (
            f"<think>\n"
            f"1. Tóm tắt dữ kiện:\n"
            f"- Diện tích hồ A = Diện tích hồ B = S_lake.\n"
            f"- Tốc độ sinh trưởng: r = 2 (nhân đôi mỗi ngày).\n"
            f"- Hồ A: Khởi đầu 1 cụm, đầy hồ sau {days_A} ngày => S_lake = S_0 * 2^{days_A}.\n"
            f"- Hồ B: Khởi đầu {k} cụm bèo (với {k} = 2^{m}).\n\n"
            f"2. Bẫy tư duy:\n"
            f"- Tuyệt đối không lấy {days_A} chia cho {k} = {days_A / k:.2f} ngày (bẫy ngụy biện tỉ lệ tuyến tính).\n\n"
            f"3. Suy luận toán học:\n"
            f"- Diện tích hồ B sau t_B ngày: S_B(t_B) = {k} * S_0 * 2^{{t_B}} = 2^{m} * S_0 * 2^{{t_B}} = S_0 * 2^{{m + t_B}}.\n"
            f"- Khi hồ B đầy: S_0 * 2^{{m + t_B}} = S_0 * 2^{days_A} => m + t_B = {days_A} => t_B = {days_A} - {m} = {days_B} ngày.\n"
            f"- Thời gian hồ B phủ kín trước hồ A là: {days_A} - {days_B} = {m} ngày.\n"
            f"- Kiểm tra lại: {days_B} ngày phát triển từ {k} cụm là hoàn toàn chính xác.\n"
            f"</think>"
        )

        answer = (
            f"1. Hồ B mất **{days_B} ngày** để phủ kín toàn bộ mặt hồ.\n"
            f"2. Hồ B phủ kín trước hồ A **{m} ngày**.\n\n"
            f"*(Giải thích: Vì {k} = 2^{m}, lượng bèo ban đầu của hồ B đã bằng đúng lượng bèo hồ A đạt được sau {m} ngày. "
            f"Do đó hồ B đi trước {m} ngày so với hồ A).* "
        )

        return {
            "category": "exponential_growth_lilypad",
            "difficulty": "medium",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }


# ==============================================================================
# 2. CHARACTER DECOMPOSITION & COUNTING GENERATOR
# ==============================================================================
class LetterDecompositionGenerator:
    """Generates letter counting problems with explicit token-by-token decomposition."""

    WORDS_EN = [
        ("strawberry", "r"),
        ("strawberry", "a"),
        ("strawberry", "e"),
        ("strawberry", "z"),
        ("occurrence", "c"),
        ("occurrence", "r"),
        ("occurrence", "e"),
        ("occurrence", "o"),
        ("mississippi", "s"),
        ("mississippi", "i"),
        ("mississippi", "p"),
        ("mississippi", "m"),
        ("millennium", "l"),
        ("millennium", "n"),
        ("millennium", "m"),
        ("millennium", "e"),
        ("accommodation", "c"),
        ("accommodation", "m"),
        ("accommodation", "o"),
        ("embarrassment", "r"),
        ("embarrassment", "s"),
        ("embarrassment", "a"),
        ("indivisibility", "i"),
        ("indivisibility", "d"),
        ("bookkeeper", "e"),
        ("bookkeeper", "o"),
        ("bookkeeper", "k"),
        ("banana", "a"),
        ("banana", "n"),
        ("banana", "b"),
        ("success", "s"),
        ("success", "c"),
        ("parallel", "l"),
        ("parallel", "a"),
        ("committee", "m"),
        ("committee", "t"),
        ("committee", "e"),
        ("possession", "s"),
        ("possession", "o"),
        ("consciousness", "s"),
        ("consciousness", "c"),
        ("consciousness", "n"),
        ("rhythm", "h"),
        ("rhythm", "y"),
        ("rhythm", "e"),
        ("queue", "u"),
        ("queue", "e"),
        ("unbelievable", "e"),
        ("unbelievable", "l"),
        ("artificial", "i"),
        ("artificial", "a"),
        ("intelligence", "l"),
        ("intelligence", "e"),
        ("intelligence", "i"),
        ("intelligence", "n"),
        ("antigravity", "t"),
        ("antigravity", "i"),
        ("antigravity", "a"),
        ("supercalifragilisticexpialidocious", "i"),
        ("supercalifragilisticexpialidocious", "c"),
        ("supercalifragilisticexpialidocious", "l"),
        ("disproportionate", "o"),
        ("disproportionate", "p"),
        ("disproportionate", "r"),
    ]

    WORDS_VI = [
        ("nghiêng ngả", "n"),
        ("nghiêng ngả", "g"),
        ("nghiêng ngả", "i"),
        ("nghiêng ngả", "a"),
        ("thanh long ruột đỏ", "h"),
        ("thanh long ruột đỏ", "o"),
        ("thanh long ruột đỏ", "t"),
        ("thanh long ruột đỏ", "n"),
        ("trường đại học bách khoa", "h"),
        ("trường đại học bách khoa", "a"),
        ("trường đại học bách khoa", "c"),
        ("trường đại học bách khoa", "o"),
        ("hoa bèo nở rộ", "o"),
        ("hoa bèo nở rộ", "b"),
        ("hoa bèo nở rộ", "h"),
        ("suy luận logic", "l"),
        ("suy luận logic", "u"),
        ("suy luận logic", "c"),
        ("chúc mừng năm mới", "m"),
        ("chúc mừng năm mới", "n"),
        ("chúc mừng năm mới", "c"),
        ("ngập ngừng", "n"),
        ("ngập ngừng", "g"),
        ("nghĩ ngợi", "n"),
        ("nghĩ ngợi", "g"),
        ("lấp lánh", "l"),
        ("lấp lánh", "h"),
        ("bát ngát", "a"),
        ("bát ngát", "t"),
        ("việt nam thịnh vượng", "n"),
        ("việt nam thịnh vượng", "t"),
        ("việt nam thịnh vượng", "h"),
        ("trí tuệ nhân tạo", "t"),
        ("trí tuệ nhân tạo", "n"),
        ("trí tuệ nhân tạo", "a"),
        ("khoa học máy tính", "h"),
        ("khoa học máy tính", "a"),
        ("khoa học máy tính", "t"),
        ("tư duy phản biện", "n"),
        ("tư duy phản biện", "h"),
        ("tư duy phản biện", "i"),
        ("hàm mũ hoa bèo", "o"),
        ("hàm mũ hoa bèo", "b"),
        ("hàm mũ hoa bèo", "a"),
    ]

    def __init__(self, rng: random.Random):
        self.rng = rng

    def generate(self) -> Dict[str, Any]:
        is_vietnamese = self.rng.random() < 0.6
        if is_vietnamese:
            word, target_char = self.rng.choice(self.WORDS_VI)
            return self._gen_vi(word, target_char)
        else:
            word, target_char = self.rng.choice(self.WORDS_EN)
            return self._gen_en(word, target_char)

    def _gen_vi(self, phrase: str, target: str) -> Dict[str, Any]:
        clean_phrase = phrase.lower()
        target_char = target.lower()

        question_templates = [
            f"Trong cụm từ \"{phrase}\", chữ cái '{target_char}' xuất hiện bao nhiêu lần?",
            f"Hãy đếm số lần xuất hiện của ký tự '{target_char}' trong chuỗi \"{phrase}\".",
            f"Có tất cả bao nhiêu chữ '{target_char}' trong từ \"{phrase}\"? Hãy phân tích chi tiết từng vị trí.",
            f"Đếm chính xác số lượng chữ cái '{target_char}' trong cụm từ \"{phrase}\"."
        ]
        question = self.rng.choice(question_templates)

        chars = list(clean_phrase)
        matching_indices = []
        decomposition_lines = []

        for idx, ch in enumerate(chars, 1):
            if ch == " ":
                decomposition_lines.append(f"{idx}. Ký tự [dấu cách] (vị trí {idx}) - bỏ qua")
                continue
            is_match = (ch == target_char)
            if is_match:
                matching_indices.append(idx)
                decomposition_lines.append(f"{idx}. '{ch}' (vị trí {idx}) -> KHỚP với '{target_char}' (lần thứ {len(matching_indices)})")
            else:
                decomposition_lines.append(f"{idx}. '{ch}' (vị trí {idx}) -> không khớp")

        total_count = len(matching_indices)
        indices_str = ", ".join(map(str, matching_indices)) if matching_indices else "không có"

        think = (
            f"<think>\n"
            f"1. Xác định yêu cầu bài toán:\n"
            f"- Chuỗi cần kiểm tra: \"{phrase}\"\n"
            f"- Ký tự cần đếm: '{target_char}' (không phân biệt chữ hoa/chữ thường)\n\n"
            f"2. Lý do cần phân rã ký tự (Tránh bẫy BPE / Subword Tokenization):\n"
            f"- Các mô hình ngôn ngữ lớn (LLM) thường xử lý chuỗi dưới dạng các subword token "
            f"thay vì từng ký tự độc lập, dẫn đến việc đếm sai các chữ cái lặp lại hoặc nằm giữa từ.\n"
            f"- Để đảm bảo độ chính xác tuyệt đối 100%, ta sẽ tách rời toàn bộ chuỗi thành từng ký tự và đánh chỉ mục từ 1 đến hết:\n\n"
            f"3. Bảng phân rã chi tiết từng ký tự:\n"
            + "\n".join(decomposition_lines) +
            f"\n\n4. Tổng kết thống kê:\n"
            f"- Tổng chiều dài chuỗi: {len(chars)} ký tự (bao gồm cả dấu cách).\n"
            f"- Các vị trí xuất hiện ký tự '{target_char}': [{indices_str}].\n"
            f"- Tổng số lần xuất hiện: {total_count}.\n"
            f"- Kiểm chứng lại: Quét đối chiếu lần 2 xác nhận đúng chính xác {total_count} ký tự '{target_char}'.\n"
            f"</think>"
        )

        if total_count > 0:
            answer = (
                f"Trong cụm từ \"{phrase}\", chữ cái '{target_char}' xuất hiện chính xác **{total_count}** lần "
                f"(tại các vị trí: {indices_str})."
            )
        else:
            answer = (
                f"Trong cụm từ \"{phrase}\", chữ cái '{target_char}' **không xuất hiện lần nào** (0 lần)."
            )

        return {
            "category": "character_decomposition_counting",
            "difficulty": "medium",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_en(self, word: str, target: str) -> Dict[str, Any]:
        clean_word = word.lower()
        target_char = target.lower()

        templates = [
            f"How many times does the letter '{target_char}' appear in the word \"{word}\"?",
            f"How many '{target_char}'s are in \"{word}\"? Count them step by step.",
            f"Count the exact occurrences of the letter '{target_char}' in \"{word}\".",
            f"In the word \"{word}\", how many times does the character '{target_char}' appear?"
        ]
        question = self.rng.choice(templates)

        chars = list(clean_word)
        matching_indices = []
        lines = []

        for idx, ch in enumerate(chars, 1):
            is_match = (ch == target_char)
            if is_match:
                matching_indices.append(idx)
                lines.append(f"Position {idx}: '{ch}' -> MATCH '{target_char}' (Count: {len(matching_indices)})")
            else:
                lines.append(f"Position {idx}: '{ch}' -> no match")

        total_count = len(matching_indices)
        indices_str = ", ".join(map(str, matching_indices)) if matching_indices else "none"

        think = (
            f"<think>\n"
            f"1. Problem objective: Count the number of '{target_char}' characters in \"{word}\".\n"
            f"2. Methodological motivation:\n"
            f"- Standard subword tokenizers treat words as single tokens, causing tokenization bias and hallucinations.\n"
            f"- To guarantee 100% precision, we perform an explicit character-level decomposition with 1-based indexing:\n\n"
            f"3. Step-by-step character inspection:\n"
            + "\n".join(lines) +
            f"\n\n4. Synthesis & Verification:\n"
            f"- Word length: {len(chars)} letters.\n"
            f"- Matching indices for '{target_char}': [{indices_str}].\n"
            f"- Final verified count: {total_count}.\n"
            f"</think>"
        )

        if total_count > 0:
            answer = (
                f"The letter '{target_char}' appears exactly **{total_count}** time{'s' if total_count != 1 else ''} "
                f"in the word \"{word}\" (at position{'s' if total_count != 1 else ''}: {indices_str})."
            )
        else:
            answer = (
                f"The letter '{target_char}' appears **0** times in the word \"{word}\"."
            )

        return {
            "category": "character_decomposition_counting",
            "difficulty": "medium",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_EN},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }


# ==============================================================================
# 3. TRUTH/LIAR (KNIGHTS & KNAVES) LOGIC GENERATOR
# ==============================================================================
class KnightsAndKnavesGenerator:
    """Generates sound truth/liar logic puzzles with rigorous proof by contradiction."""

    NAME_PAIRS = [
        ("An", "Bình"),
        ("Minh", "Nam"),
        ("Khôi", "Long"),
        ("Quang", "Huy"),
        ("Alice", "Bob"),
        ("David", "Edward")
    ]

    NAME_TRIPLETS = [
        ("An", "Bình", "Cường"),
        ("Minh", "Nam", "Long"),
        ("Alice", "Bob", "Charlie"),
        ("Alex", "Brian", "Chris")
    ]

    def __init__(self, rng: random.Random):
        self.rng = rng

    def generate(self) -> Dict[str, Any]:
        puzzle_type = self.rng.choice([
            "two_both_liars",
            "two_at_least_one_liar",
            "two_a_claims_b_liar_b_same",
            "two_both_truth_b_claims_a_liar",
            "two_different_types",
            "three_classic_knaves_knight_contradiction",
            "three_cyclic_accusation"
        ])

        if puzzle_type == "two_both_liars":
            return self._gen_two_both_liars()
        elif puzzle_type == "two_at_least_one_liar":
            return self._gen_two_at_least_one_liar()
        elif puzzle_type == "two_a_claims_b_liar_b_same":
            return self._gen_two_a_claims_b_liar_b_same()
        elif puzzle_type == "two_both_truth_b_claims_a_liar":
            return self._gen_two_both_truth_b_claims_a_liar()
        elif puzzle_type == "two_different_types":
            return self._gen_two_different_types()
        elif puzzle_type == "three_classic_knaves_knight_contradiction":
            return self._gen_three_classic()
        else:
            return self._gen_three_cyclic()

    def _gen_two_both_liars(self) -> Dict[str, Any]:
        p1, p2 = self.rng.choice(self.NAME_PAIRS)
        question = (
            f"Trên một hòn đảo kỳ bí chỉ có hai loại cư dân: Người Thật Thà (luôn luôn nói thật) và Kẻ Gian Xảo (luôn luôn nói dối). "
            f"Bạn gặp hai người bản địa tên là {p1} và {p2}.\n"
            f"{p1} tuyên bố: \"Cả hai chúng tôi đều là Kẻ Gian Xảo.\"\n"
            f"Hỏi {p1} và {p2} mỗi người là Người Thật Thà hay Kẻ Gian Xảo?"
        )

        think = (
            f"<think>\n"
            f"1. Phân tích luật chơi:\n"
            f"- Người Thật Thà (Knight): Mọi lời nói luôn ĐÚNG (True).\n"
            f"- Kẻ Gian Xảo (Knave): Mọi lời nói luôn SAI (False).\n"
            f"- Lời phát biểu của {p1}: \"Cả {p1} và {p2} đều là Kẻ Gian Xảo.\"\n\n"
            f"2. Xét Giả thuyết 1: Giả sử {p1} là Người Thật Thà.\n"
            f"- Nếu {p1} là Người Thật Thà, thì phát biểu của {p1} phải là ĐÚNG.\n"
            f"- Điều đó có nghĩa là: \"Cả {p1} và {p2} đều là Kẻ Gian Xảo\".\n"
            f"- Suy ra {p1} phải là Kẻ Gian Xảo.\n"
            f"- Mâu thuẫn logic: {p1} vừa là Người Thật Thà vừa là Kẻ Gian Xảo! (Vô lý).\n"
            f"=> Do đó, Giả thuyết 1 SAI. {p1} không thể là Người Thật Thà.\n\n"
            f"3. Xét Giả thuyết 2: {p1} là Kẻ Gian Xảo.\n"
            f"- Vì {p1} là Kẻ Gian Xảo, nên phát biểu của {p1} phải là SAI.\n"
            f"- Phủ định của mệnh đề (\"Cả hai chúng tôi đều là Kẻ Gian Xảo\") là: Ít nhất một trong hai người KHÔNG PHẢI là Kẻ Gian Xảo (tức là có ít nhất một Người Thật Thà).\n"
            f"- Vì bản thân {p1} đã là Kẻ Gian Xảo, nên Người Thật Thà duy nhất đó bắt buộc phải là {p2}.\n"
            f"- Suy ra {p2} là Người Thật Thà.\n\n"
            f"4. Kiểm tra tính nhất quán toàn cục:\n"
            f"- {p1}: Kẻ Gian Xảo. Phát biểu: \"Cả hai là Kẻ Gian Xảo\" -> SAI. Nhất quán với bản chất Kẻ Gian Xảo.\n"
            f"- {p2}: Người Thật Thà. Nhất quán.\n"
            f"- Kết luận duy nhất và chuẩn xác: {p1} là Kẻ Gian Xảo, {p2} là Người Thật Thà.\n"
            f"</think>"
        )

        answer = (
            f"Kết luận:\n"
            f"- **{p1} là Kẻ Gian Xảo** (nói dối).\n"
            f"- **{p2} là Người Thật Thà** (nói thật).\n\n"
            f"*(Bởi vì nếu {p1} nói thật thì việc tự nhận mình là kẻ gian xảo sẽ gây mâu thuẫn. "
            f"Vậy {p1} nói dối, kéo theo lời tuyên bố 'cả hai đều nói dối' là sai, chứng tỏ {p2} là người nói thật).*"
        )

        return {
            "category": "logic_truth_liar",
            "difficulty": "medium",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_two_at_least_one_liar(self) -> Dict[str, Any]:
        p1, p2 = self.rng.choice(self.NAME_PAIRS)
        question = (
            f"Tại Đảo Thật - Dối (nơi Người Thật Thà luôn nói thật, Kẻ Gian Xảo luôn nói dối), bạn gặp hai người {p1} và {p2}.\n"
            f"{p1} nói: \"Ít nhất một trong hai chúng tôi là Kẻ Gian Xảo.\"\n"
            f"Hỏi chính xác danh tính của {p1} và {p2} là gì?"
        )

        think = (
            f"<think>\n"
            f"1. Xác định quy tắc:\n"
            f"- Knight: Nói thật (True).\n"
            f"- Knave: Nói dối (False).\n"
            f"- Phát biểu của {p1}: \"Ít nhất một trong hai người ({p1} hoặc {p2}) là Knave\".\n\n"
            f"2. Xét trường hợp {p1} là Knave (Kẻ Gian Xảo):\n"
            f"- Nếu {p1} là Knave thì lời {p1} nói là SAI.\n"
            f"- Phủ định của \"ít nhất một người là Knave\" là: \"Cả hai người đều là Knight (Người Thật Thà)\".\n"
            f"- Như vậy kéo theo {p1} là Knight. Nhưng ta đang giả định {p1} là Knave -> MÂU THUẪN LOGIC!\n"
            f"- Do đó {p1} không thể là Knave. Bắt buộc {p1} phải là Knight.\n\n"
            f"3. Suy ra danh tính của {p2}:\n"
            f"- Vì {p1} là Knight, phát biểu của {p1} là ĐÚNG.\n"
            f"- Tức là: \"Ít nhất một trong hai người là Knave\".\n"
            f"- Vì {p1} đã là Knight, nên người Knave còn lại bắt buộc phải là {p2}.\n\n"
            f"4. Kiểm tra lại:\n"
            f"- {p1} là Knight, {p2} là Knave.\n"
            f"- Có đúng 1 người là Knave ({p2}), nên mệnh đề \"ít nhất một người là Knave\" là ĐÚNG. Phù hợp hoàn hảo.\n"
            f"</think>"
        )

        answer = (
            f"Kết luận:\n"
            f"- **{p1} là Người Thật Thà** (Knight).\n"
            f"- **{p2} là Kẻ Gian Xảo** (Knave)."
        )

        return {
            "category": "logic_truth_liar",
            "difficulty": "medium",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_two_a_claims_b_liar_b_same(self) -> Dict[str, Any]:
        p1, p2 = self.rng.choice(self.NAME_PAIRS)
        question = (
            f"Trên hòn đảo của các Hiệp sĩ (luôn nói thật) và Kẻ lừa dối (luôn nói dối), bạn gặp {p1} và {p2}.\n"
            f"{p1} nói: \"{p2} là Kẻ lừa dối.\"\n"
            f"{p2} nói: \"{p1} và tôi thuộc cùng một loại người.\"\n"
            f"Hãy xác định xem ai là Hiệp sĩ và ai là Kẻ lừa dối."
        )

        think = (
            f"<think>\n"
            f"1. Phân tích các phát biểu:\n"
            f"- Phát biểu của {p1}: \"{p2} là Kẻ lừa dối\".\n"
            f"- Phát biểu của {p2}: \"{p1} và tôi thuộc cùng một loại người\".\n\n"
            f"2. Xét Giả thuyết 1: {p1} là Hiệp sĩ (nói thật):\n"
            f"- Khi {p1} nói thật => Phát biểu \"{p2} là Kẻ lừa dối\" là ĐÚNG.\n"
            f"- Do đó {p2} là Kẻ lừa dối.\n"
            f"- Vì {p2} là Kẻ lừa dối, phát biểu của {p2} (\"cùng một loại người\") phải là SAI.\n"
            f"- Kiểm tra: {p1} là Hiệp sĩ, {p2} là Kẻ lừa dối -> họ khác loại người -> Phát biểu \"cùng loại\" của {p2} quả thực là SAI!\n"
            f"- Toàn bộ các phát biểu hoàn toàn KHỚP và không có mâu thuẫn.\n\n"
            f"3. Xét Giả thuyết 2: {p1} là Kẻ lừa dối (nói dối):\n"
            f"- Khi {p1} nói dối => Phát biểu \"{p2} là Kẻ lừa dối\" là SAI.\n"
            f"- Do đó {p2} phải là Hiệp sĩ.\n"
            f"- Vì {p2} là Hiệp sĩ, phát biểu của {p2} (\"cùng một loại người\") phải là ĐÚNG.\n"
            f"- Tuy nhiên, {p1} là Kẻ lừa dối và {p2} là Hiệp sĩ thì họ khác loại người -> Phát biểu của {p2} là SAI!\n"
            f"- Điều này mâu thuẫn với việc {p2} là Hiệp sĩ! MÂU THUẪN LOGIC.\n\n"
            f"4. Kết luận:\n"
            f"- Chỉ có Giả thuyết 1 là nghiệm hợp lệ duy nhất: {p1} là Hiệp sĩ, {p2} là Kẻ lừa dối.\n"
            f"</think>"
        )

        answer = (
            f"Đáp án chính xác:\n"
            f"- **{p1} là Hiệp sĩ** (Người nói thật).\n"
            f"- **{p2} là Kẻ lừa dối** (Kẻ nói dối)."
        )

        return {
            "category": "logic_truth_liar",
            "difficulty": "medium",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_two_both_truth_b_claims_a_liar(self) -> Dict[str, Any]:
        p1, p2 = self.rng.choice(self.NAME_PAIRS)
        question = (
            f"Tại Đảo Logic (Hiệp sĩ nói thật, Kẻ nói dối luôn nói sai), bạn gặp hai người {p1} và {p2}.\n"
            f"{p1} tuyên bố: \"Cả hai chúng tôi đều là Hiệp sĩ nói thật.\"\n"
            f"{p2} tuyên bố: \"{p1} là Kẻ nói dối.\"\n"
            f"Hãy phân tích và cho biết danh tính chính xác của mỗi người."
        )

        think = (
            f"<think>\n"
            f"1. Phân tích đề bài:\n"
            f"- {p1}: \"Cả hai chúng tôi đều là Hiệp sĩ\".\n"
            f"- {p2}: \"{p1} là Kẻ nói dối\".\n\n"
            f"2. Giả sử {p1} là Hiệp sĩ:\n"
            f"- Phát biểu của {p1} là ĐÚNG => Cả {p1} và {p2} đều là Hiệp sĩ.\n"
            f"- Nếu {p2} là Hiệp sĩ thì lời {p2} nói phải ĐÚNG: \"{p1} là Kẻ nói dối\".\n"
            f"- Điều này mâu thuẫn trực tiếp với việc {p1} là Hiệp sĩ! (Vô lý).\n"
            f"=> Giả thiết {p1} là Hiệp sĩ bị loại bỏ hoàn toàn.\n\n"
            f"3. Vậy {p1} bắt buộc là Kẻ nói dối:\n"
            f"- Khi {p1} là Kẻ nói dối, phát biểu \"Cả hai là Hiệp sĩ\" là SAI (hoàn toàn phù hợp).\n"
            f"- Bây giờ xét {p2}: {p2} nói \"{p1} là Kẻ nói dối\".\n"
            f"- Vì {p1} thực sự là Kẻ nói dối, nên lời nói của {p2} là ĐÚNG!\n"
            f"- Một người nói đúng thì bắt buộc phải là Hiệp sĩ.\n"
            f"- Vậy {p2} là Hiệp sĩ.\n\n"
            f"4. Kiểm tra tính tương thích:\n"
            f"- {p1}: Kẻ nói dối (nói sai -> khớp).\n"
            f"- {p2}: Hiệp sĩ (nói đúng -> khớp).\n"
            f"- Không tồn tại bất kỳ mâu thuẫn nào.\n"
            f"</think>"
        )

        answer = (
            f"Kết luận:\n"
            f"- **{p1} là Kẻ nói dối**.\n"
            f"- **{p2} là Hiệp sĩ** (Người nói thật)."
        )

        return {
            "category": "logic_truth_liar",
            "difficulty": "medium",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_two_different_types(self) -> Dict[str, Any]:
        p1, p2 = self.rng.choice(self.NAME_PAIRS)
        question = (
            f"Gặp hai người {p1} và {p2} trên đảo Hiệp sĩ (nói thật) và Kẻ gian (nói dối).\n"
            f"{p1} nói: \"Chúng tôi thuộc hai loại người khác nhau.\"\n"
            f"{p2} nói: \"{p1} là Kẻ gian nói dối.\"\n"
            f"Xác định danh tính của từng người."
        )

        think = (
            f"<think>\n"
            f"1. Phân tích các khả năng cho {p1}:\n"
            f"- Trường hợp A: Giả sử {p1} là Hiệp sĩ (nói thật):\n"
            f"  + Lời {p1} nói là ĐÚNG: Họ thuộc hai loại người khác nhau.\n"
            f"  + Vì {p1} là Hiệp sĩ, nên {p2} bắt buộc phải là Kẻ gian.\n"
            f"  + Xét phát biểu của {p2}: \"{p1} là Kẻ gian nói dối\".\n"
            f"  + Vì {p1} là Hiệp sĩ, nên lời của {p2} là SAI.\n"
            f"  + Một Kẻ gian đưa ra phát biểu SAI là hoàn toàn nhất quán!\n"
            f"  => Trường hợp A hợp lệ.\n\n"
            f"- Trường hợp B: Giả sử {p1} là Kẻ gian (nói dối):\n"
            f"  + Lời {p1} nói là SAI: Phủ định của \"khác loại\" là \"cùng loại người\".\n"
            f"  + Vậy cả {p1} và {p2} đều là Kẻ gian.\n"
            f"  + Xét phát biểu của {p2}: \"{p1} là Kẻ gian nói dối\".\n"
            f"  + Vì {p1} là Kẻ gian, nên phát biểu của {p2} là ĐÚNG!\n"
            f"  + Nhưng {p2} đang được giả định là Kẻ gian (phải luôn nói sai) -> MÂU THUẪN LOGIC!\n"
            f"  => Trường hợp B bị loại.\n\n"
            f"2. Kết luận duy nhất: {p1} là Hiệp sĩ, {p2} là Kẻ gian.\n"
            f"</think>"
        )

        answer = (
            f"Kết quả phân tích:\n"
            f"- **{p1} là Hiệp sĩ** (Người nói thật).\n"
            f"- **{p2} là Kẻ gian** (Kẻ nói dối)."
        )

        return {
            "category": "logic_truth_liar",
            "difficulty": "medium",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_three_classic(self) -> Dict[str, Any]:
        p1, p2, p3 = self.rng.choice(self.NAME_TRIPLETS)
        question = (
            f"Trên đảo chỉ có Hiệp sĩ (luôn nói thật) và Kẻ nói dối (luôn nói dối), bạn gặp 3 người {p1}, {p2} và {p3}.\n"
            f"- {p1} tuyên bố: \"Tất cả ba chúng tôi đều là Kẻ nói dối.\"\n"
            f"- {p2} tuyên bố: \"Chính xác chỉ có đúng một người trong ba chúng tôi là Hiệp sĩ nói thật.\"\n"
            f"- {p3} tuyên bố: \"{p2} là Kẻ nói dối.\"\n"
            f"Hãy xác định rõ mỗi người {p1}, {p2}, {p3} thuộc loại nào?"
        )

        think = (
            f"<think>\n"
            f"1. Xét phát biểu của {p1}: \"Cả 3 chúng tôi đều là Kẻ nói dối\".\n"
            f"- Nếu {p1} là Hiệp sĩ -> {p1} nói thật -> cả 3 đều là Kẻ nói dối -> {p1} là Kẻ nói dối (Mâu thuẫn!).\n"
            f"- Do đó {p1} chắc chắn là Kẻ nói dối.\n"
            f"- Khi {p1} là Kẻ nói dối, mệnh đề \"cả 3 đều nói dối\" là SAI (nghĩa là có ít nhất 1 Hiệp sĩ trong nhóm).\n\n"
            f"2. Xét phát biểu của {p2} và {p3}:\n"
            f"- {p3} nói: \"{p2} là Kẻ nói dối\".\n"
            f"- Điều này có nghĩa {p2} và {p3} có giá trị chân lý đối nghịch nhau (một người là Hiệp sĩ, người kia là Kẻ nói dối).\n"
            f"- Ta kiểm tra hai trường hợp:\n\n"
            f"  * Giả thuyết A: Giả sử {p2} là Hiệp sĩ (nói thật).\n"
            f"    + Vì {p2} là Hiệp sĩ, nên lời của {p2} là ĐÚNG: \"Chính xác chỉ có đúng một người là Hiệp sĩ\".\n"
            f"    + Hiệp sĩ duy nhất đó chính là {p2}.\n"
            f"    + Suy ra {p1} là Kẻ nói dối, {p3} là Kẻ nói dối.\n"
            f"    + Kiểm tra lại lời {p3}: {p3} nói \"{p2} là Kẻ nói dối\". Vì {p2} là Hiệp sĩ, nên {p3} nói SAI. Điều này hoàn toàn khớp với việc {p3} là Kẻ nói dối!\n"
            f"    + Tất cả các điều kiện đều thỏa mãn hoàn hảo.\n\n"
            f"  * Giả thuyết B: Giả sử {p2} là Kẻ nói dối.\n"
            f"    + Vì {p2} là Kẻ nói dối, nên {p3} (người bảo \"{p2} nói dối\") nói ĐÚNG => {p3} là Hiệp sĩ.\n"
            f"    + Khi đó số lượng Hiệp sĩ là: {p1} (nói dối), {p2} (nói dối), {p3} (Hiệp sĩ) -> có đúng 1 Hiệp sĩ duy nhất ({p3}).\n"
            f"    + Nhưng nếu có đúng 1 Hiệp sĩ, thì phát biểu của {p2} (\"Chính xác có đúng 1 Hiệp sĩ\") lại trở thành sự thật!\n"
            f"    + Điều này mâu thuẫn với việc {p2} là Kẻ nói dối! (Mâu thuẫn logic loại trừ).\n\n"
            f"3. Kết luận duy nhất không có mâu thuẫn:\n"
            f"- {p1} là Kẻ nói dối.\n"
            f"- {p2} là Hiệp sĩ.\n"
            f"- {p3} là Kẻ nói dối.\n"
            f"</think>"
        )

        answer = (
            f"Danh tính của 3 người là:\n"
            f"- **{p1} là Kẻ nói dối**.\n"
            f"- **{p2} là Hiệp sĩ** (Người nói thật).\n"
            f"- **{p3} là Kẻ nói dối**.\n\n"
            f"*(Chỉ có cấu hình này mới không sinh ra bất kỳ nghịch lý logic nào).* "
        )

        return {
            "category": "logic_truth_liar",
            "difficulty": "hard",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_three_cyclic(self) -> Dict[str, Any]:
        p1, p2, p3 = self.rng.choice(self.NAME_TRIPLETS)
        question = (
            f"Ba cư dân {p1}, {p2}, {p3} đứng cạnh nhau trên đảo Hiệp sĩ / Kẻ lừa dối.\n"
            f"- {p1} bảo: \"{p2} là Kẻ lừa dối.\"\n"
            f"- {p2} bảo: \"{p3} là Kẻ lừa dối.\"\n"
            f"- {p3} bảo: \"{p1} và {p2} đều là Kẻ lừa dối.\"\n"
            f"Hãy chỉ rõ danh tính thật sự của cả 3 người."
        )

        think = (
            f"<think>\n"
            f"1. Phân tích bài toán:\n"
            f"- {p1} -> ~{p2}\n"
            f"- {p2} -> ~{p3}\n"
            f"- {p3} -> (~{p1} VÀ ~{p2})\n\n"
            f"2. Xét Giả thuyết 1: Giả sử {p1} là Hiệp sĩ (T):\n"
            f"- {p1} nói thật => {p2} là Kẻ lừa dối (F).\n"
            f"- {p2} là F => Lời của {p2} (\"~{p3}\") là SAI => {p3} là Hiệp sĩ (T).\n"
            f"- {p3} là Hiệp sĩ (T) => Lời của {p3} (\"~{p1} và ~{p2}\") phải là ĐÚNG.\n"
            f"- Nhưng ta đang giả sử {p1} là Hiệp sĩ! Mệnh đề \"~{p1} và ~{p2}\" là SAI!\n"
            f"- Mâu thuẫn logic: {p3} vừa là Hiệp sĩ vừa nói sai -> Loại bỏ Giả thuyết 1.\n\n"
            f"3. Xét Giả thuyết 2: {p1} là Kẻ lừa dối (F):\n"
            f"- {p1} nói dối => Lời {p1} (\"~{p2}\") là SAI => {p2} là Hiệp sĩ (T).\n"
            f"- {p2} là Hiệp sĩ (T) => Lời của {p2} (\"~{p3}\") là ĐÚNG => {p3} là Kẻ lừa dối (F).\n"
            f"- Bây giờ kiểm tra {p3}: Lời {p3} là \"{p1} và {p2} đều là Kẻ lừa dối\".\n"
            f"- Vì {p2} là Hiệp sĩ, nên lời của {p3} là SAI. Điều này hoàn toàn khớp với việc {p3} là Kẻ lừa dối (F)!\n"
            f"- Tất cả đều nhất quán 100%.\n\n"
            f"4. Kết luận chuẩn xác:\n"
            f"- {p1}: Kẻ lừa dối.\n"
            f"- {p2}: Hiệp sĩ.\n"
            f"- {p3}: Kẻ lừa dối.\n"
            f"</think>"
        )

        answer = (
            f"Danh tính được xác định chính xác như sau:\n"
            f"- **{p1} là Kẻ lừa dối** (Knave).\n"
            f"- **{p2} là Hiệp sĩ** (Knight).\n"
            f"- **{p3} là Kẻ lừa dối** (Knave)."
        )

        return {
            "category": "logic_truth_liar",
            "difficulty": "hard",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }


# ==============================================================================
# 4. CLASSIC COGNITIVE TRAPS & MATH REASONING GENERATOR
# ==============================================================================
class CognitiveTrapMathGenerator:
    """Generates classic cognitive reflection tests and mathematical traps."""

    BAT_BALL_ITEMS = [
        ("gậy bóng chày", "quả bóng", 1.10, 1.00, "$", "đô la"),
        ("vợt bóng bàn", "quả bóng", 220000, 200000, "đ", "đồng"),
        ("quyển sách", "chiếc bút bi", 110000, 100000, "đ", "đồng"),
        ("chiếc áo khoác", "đôi găng tay", 120, 100, "$", "đô la"),
        ("xe máy điện", "mũ bảo hiểm", 21000000, 20000000, "đ", "đồng"),
        ("máy ảnh kỹ thuật số", "thẻ nhớ SD", 10500000, 10000000, "đ", "đồng"),
        ("bộ máy tính laptop", "con chuột không dây", 25500000, 25000000, "đ", "đồng"),
        ("chiếc vali du lịch", "thẻ tên hành lý", 55, 50, "$", "đô la"),
        ("cặp vé xem hòa nhạc", "nước uống", 520000, 500000, "đ", "đồng"),
        ("tách cà phê", "chiếc bánh ngọt", 4.50, 3.50, "$", "đô la"),
    ]

    MACHINE_RATES = [
        (5, 5, 5, 100, 100, "máy", "phút", "sản phẩm"),
        (10, 10, 10, 50, 50, "máy may", "phút", "bộ quần áo"),
        (8, 8, 8, 64, 64, "robot tự hành", "phút", "kiện hàng"),
        (6, 6, 6, 36, 36, "máy in 3D", "giờ", "chi tiết mô hình"),
        (4, 4, 4, 20, 20, "công nhân", "ngày", "chiếc bàn gỗ"),
        (7, 7, 7, 49, 49, "máy dệt", "phút", "mét vải"),
    ]

    SPEED_PAIRS = [
        (60, 40, "km/h"),
        (30, 20, "km/h"),
        (120, 80, "km/h"),
        (90, 60, "km/h"),
        (50, 30, "km/h"),
        (40, 60, "km/h"),
        (100, 50, "km/h")
    ]

    PALINDROME_WORDS = [
        ("radar", True),
        ("rotator", True),
        ("deified", True),
        ("civic", True),
        ("kayak", True),
        ("madam", True),
        ("refer", True),
        ("level", True),
        ("noon", True),
        ("racecar", True),
        ("12321", True),
        ("algorithm", False),
        ("strawberry", False),
        ("antigravity", False),
        ("computer", False),
        ("palindrome", False),
        ("banana", False),
        ("python", False),
        ("learning", False),
        ("123421", False),
    ]

    def __init__(self, rng: random.Random):
        self.rng = rng

    def generate(self) -> Dict[str, Any]:
        trap_type = self.rng.choice([
            "bat_and_ball",
            "machine_work_rate",
            "snail_climbing_well",
            "harmonic_mean_speed",
            "palindrome_check"
        ])

        if trap_type == "bat_and_ball":
            return self._gen_bat_and_ball()
        elif trap_type == "machine_work_rate":
            return self._gen_machine_work_rate()
        elif trap_type == "snail_climbing_well":
            return self._gen_snail_climbing_well()
        elif trap_type == "harmonic_mean_speed":
            return self._gen_harmonic_mean_speed()
        else:
            return self._gen_palindrome_check()

    def _gen_bat_and_ball(self) -> Dict[str, Any]:
        item1, item2, total, diff, sym, unit = self.rng.choice(self.BAT_BALL_ITEMS)
        price_item2 = (total - diff) / 2
        price_item1 = price_item2 + diff
        intuitive_trap = total - diff

        def fmt(val):
            if isinstance(val, float) and val.is_integer():
                val = int(val)
            if isinstance(val, int):
                return f"{val:,}".replace(",", ".")
            return f"{val:.2f}"

        question = (
            f"Tổng giá tiền của một {item1} và một {item2} là {fmt(total)} {unit}. "
            f"Biết rằng {item1} đắt hơn {item2} là {fmt(diff)} {unit}.\n"
            f"Hỏi giá tiền của {item2} là bao nhiêu?"
        )

        think = (
            f"<think>\n"
            f"1. Phân tích bài toán:\n"
            f"- Đặt giá tiền {item2} là x ({unit}).\n"
            f"- Giá tiền {item1} là: x + {fmt(diff)} ({unit}).\n"
            f"- Tổng giá tiền: {item1} + {item2} = {fmt(total)} ({unit}).\n\n"
            f"2. Bẫy tư duy trực giác (System 1 intuition trap):\n"
            f"- Não bộ thường phản xạ nhanh bằng cách lấy tổng trừ đi hiệu: {fmt(total)} - {fmt(diff)} = {fmt(intuitive_trap)} {unit}.\n"
            f"- Tại sao kết quả {fmt(intuitive_trap)} {unit} sai? Nếu {item2} có giá {fmt(intuitive_trap)} {unit}, thì {item1} đắt hơn {fmt(diff)} {unit} sẽ có giá là "
            f"{fmt(intuitive_trap + diff)} {unit}. Khi đó tổng tiền là {fmt(intuitive_trap)} + {fmt(intuitive_trap + diff)} = {fmt(intuitive_trap * 2 + diff)} {unit}, "
            f"vượt quá tổng đề bài cho ({fmt(total)} {unit})!\n\n"
            f"3. Thiết lập và giải phương trình đại số:\n"
            f"  x + (x + {fmt(diff)}) = {fmt(total)}\n"
            f"  <=> 2x + {fmt(diff)} = {fmt(total)}\n"
            f"  <=> 2x = {fmt(total)} - {fmt(diff)} = {fmt(total - diff)}\n"
            f"  <=> x = {fmt(total - diff)} / 2 = {fmt(price_item2)} ({unit}).\n\n"
            f"4. Kiểm chứng tính toán:\n"
            f"- Giá {item2}: {fmt(price_item2)} {unit}.\n"
            f"- Giá {item1}: {fmt(price_item2)} + {fmt(diff)} = {fmt(price_item1)} {unit}.\n"
            f"- Tổng giá tiền: {fmt(price_item1)} + {fmt(price_item2)} = {fmt(total)} {unit} (hoàn toàn chính xác).\n"
            f"- Chênh lệch: {fmt(price_item1)} - {fmt(price_item2)} = {fmt(diff)} {unit} (đúng giả thiết).\n"
            f"</think>"
        )

        answer = (
            f"Giá tiền của {item2} là **{fmt(price_item2)} {unit}**.\n\n"
            f"*(Giải thích: Nếu giá {item2} là x thì {item1} là x + {fmt(diff)}. Ta có: 2x + {fmt(diff)} = {fmt(total)} => 2x = {fmt(total - diff)} => x = {fmt(price_item2)} {unit}; "
            f"không phải là {fmt(intuitive_trap)} {unit} theo suy nghĩ vội vàng ban đầu).* "
        )

        return {
            "category": "cognitive_traps_math",
            "difficulty": "easy",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_machine_work_rate(self) -> Dict[str, Any]:
        N, T, P, M, K, unit_mach, unit_time, unit_prod = self.rng.choice(self.MACHINE_RATES)
        # N machines take T time to make P products
        # Rate per machine = P / (N * T)
        # For M machines to make K products:
        # Time = K / (M * Rate) = (K * N * T) / (M * P)
        ans_time = (K * N * T) / (M * P)
        if ans_time.is_integer():
            ans_time = int(ans_time)
        intuitive_trap = K

        question = (
            f"Nếu {N} chiếc {unit_mach} mất {T} {unit_time} để sản xuất ra {P} {unit_prod}, "
            f"thì {M} chiếc {unit_mach} cùng loại mất bao nhiêu {unit_time} để sản xuất ra {K} {unit_prod}?"
        )

        think = (
            f"<think>\n"
            f"1. Phân tích bài toán năng suất lao động:\n"
            f"- Dữ kiện 1: {N} {unit_mach} làm được {P} {unit_prod} trong {T} {unit_time}.\n"
            f"- Dữ kiện 2: Cần tìm thời gian t để {M} {unit_mach} làm được {K} {unit_prod}.\n\n"
            f"2. Bẫy tư duy trực giác:\n"
            f"- Thấy dãy số {N}-{T}-{P} (đều là {N}), não bộ thường bị hấp dẫn bởi mẫu số và đoán ngay rằng {M} {unit_mach} sẽ mất {intuitive_trap} {unit_time} để làm {K} {unit_prod}.\n"
            f"- Cần chỉ rõ: Số máy tăng lên thì năng suất chung tăng lên tương ứng.\n\n"
            f"3. Tính toán từng bước:\n"
            f"- Bước 1: Tính năng suất của 1 {unit_mach} trong 1 {unit_time}:\n"
            f"  Năng suất = Tổng sản phẩm / (Số máy * Thời gian) = {P} / ({N} * {T}) = {P / (N * T):.4f} ({unit_prod}/{unit_mach}/{unit_time}).\n"
            f"- Nhận xét: 1 {unit_mach} mất {T} {unit_time} để làm ra đúng 1 {unit_prod}.\n"
            f"- Bước 2: Khi có {M} {unit_mach} hoạt động đồng thời:\n"
            f"  Mỗi {unit_mach} chỉ cần làm: {K} / {M} = {K // M} {unit_prod}.\n"
            f"- Vì 1 {unit_mach} làm 1 {unit_prod} mất đúng {T} {unit_time}, nên để {M} {unit_mach} cùng lúc hoàn thành {K} {unit_prod} (mỗi máy làm 1 cái), "
            f"tổng thời gian cần thiết chỉ là {ans_time} {unit_time}.\n"
            f"</think>"
        )

        answer = (
            f"{M} chiếc {unit_mach} sẽ mất đúng **{ans_time} {unit_time}** để sản xuất ra {K} {unit_prod}.\n\n"
            f"*(Bởi vì 1 chiếc {unit_mach} mất {T} {unit_time} để làm ra 1 {unit_prod}. Khi có {M} {unit_mach} cùng làm đồng thời, "
            f"mỗi máy làm 1 {unit_prod} thì đúng {ans_time} {unit_time} sau toàn bộ {K} {unit_prod} sẽ được hoàn thành).* "
        )

        return {
            "category": "cognitive_traps_math",
            "difficulty": "medium",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_snail_climbing_well(self) -> Dict[str, Any]:
        H = self.rng.choice([10, 15, 20, 25, 30])
        U = self.rng.choice([3, 4, 5])
        D = self.rng.choice([1, 2])
        if D >= U:
            D = U - 1

        net = U - D
        # Days needed:
        if U >= H:
            days = 1
        else:
            prior_days = math.ceil((H - U) / net)
            days = prior_days + 1

        linear_trap = math.ceil(H / net)

        question = (
            f"Một chú ốc sên bị rơi xuống một cái giếng sâu {H} mét. "
            f"Ban ngày ốc sên leo lên được {U} mét, nhưng ban đêm khi ngủ lại bị tuột xuống {D} mét. "
            f"Hỏi sau bao nhiêu ngày chú ốc sên sẽ leo lên đến miệng giếng?"
        )

        think = (
            f"<think>\n"
            f"1. Xác định thông số bài toán:\n"
            f"- Chiều sâu giếng: H = {H} mét.\n"
            f"- Ban ngày leo lên: +{U} mét.\n"
            f"- Ban đêm trượt xuống: -{D} mét.\n"
            f"- Tiến độ ròng mỗi ngày đêm trọn vẹn: net = {U} - {D} = {net} mét.\n\n"
            f"2. Bẫy tư duy trực giác:\n"
            f"- Bẫy ngụy biện: Lấy chiều sâu giếng chia cho tiến độ ròng: {H} : {net} = {H / net:.2f} => làm tròn lên {linear_trap} ngày.\n"
            f"- Tại sao sai lầm? Khi chú ốc sên chạm tới miệng giếng ({H} mét) vào ban ngày, ốc sên ĐÃ THOÁT RA KHỎI GIẾNG và sẽ không bị tuột xuống vào ban đêm nữa!\n\n"
            f"3. Lập luận chính xác:\n"
            f"- Vào ngày cuối cùng, ốc sên leo được tối đa {U} mét.\n"
            f"- Do đó, trước ngày cuối cùng, ốc sên chỉ cần leo đến độ cao tối thiểu là: {H} - {U} = {H - U} mét.\n"
            f"- Số ngày đêm trọn vẹn cần để đạt độ cao {H - U} mét là:\n"
            f"  t_prior = ceil(({H} - {U}) / {net}) = ceil({H - U} / {net}) = {days - 1} ngày.\n"
            f"- Sau {days - 1} ngày đêm, độ cao ốc sên đạt được là: {days - 1} * {net} mét = {(days - 1) * net} mét.\n"
            f"- Sang ban ngày của ngày thứ {days}, ốc sên leo thêm {U} mét:\n"
            f"  Độ cao = {(days - 1) * net} + {U} = {(days - 1) * net + U} mét >= {H} mét.\n"
            f"- Ốc sên đã chính thức thoát khỏi miệng giếng ngay trong ban ngày của ngày thứ {days}!\n"
            f"- Vậy tổng số ngày cần thiết là đúng {days} ngày.\n"
            f"</think>"
        )

        answer = (
            f"Chú ốc sên sẽ leo lên đến miệng giếng sau đúng **{days} ngày**.\n\n"
            f"*(Giải thích: Sau {days - 1} ngày đêm đầu tiên, ốc sên đã lên được {(days - 1) * net} mét. "
            f"Vào ban ngày của ngày thứ {days}, ốc sên leo thêm {U} mét để đạt độ cao {(days - 1) * net + U} mét (vượt qua miệng giếng {H} mét) "
            f"và thoát ra ngoài, không bị tụt lại ban đêm).* "
        )

        return {
            "category": "cognitive_traps_math",
            "difficulty": "medium",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_harmonic_mean_speed(self) -> Dict[str, Any]:
        v1, v2, unit = self.rng.choice(self.SPEED_PAIRS)
        v_harm = (2 * v1 * v2) / (v1 + v2)
        v_arith = (v1 + v2) / 2
        d_sample = 120  # km

        question = (
            f"Một người đi xe máy từ thành phố A đến thành phố B với vận tốc {v1} {unit}, "
            f"sau đó quay trở về từ B về A theo cùng con đường đó với vận tốc {v2} {unit}.\n"
            f"Hỏi vận tốc trung bình của người đó trên toàn bộ chuyến đi cả đi và về là bao nhiêu {unit}?"
        )

        think = (
            f"<think>\n"
            f"1. Xác định bài toán:\n"
            f"- Quãng đường lượt đi (A -> B): d (km), vận tốc v1 = {v1} {unit}.\n"
            f"- Quãng đường lượt về (B -> A): d (km), vận tốc v2 = {v2} {unit}.\n"
            f"- Tổng quãng đường đi được: S_total = d + d = 2d.\n\n"
            f"2. Bẫy tư duy trực giác (Arithmetic Mean Fallacy):\n"
            f"- Rất nhiều người lấy trung bình cộng vận tốc: ({v1} + {v2}) / 2 = {v_arith:.1f} {unit}.\n"
            f"- Tại sao sai? Vì thời gian di chuyển ở hai chặng là khác nhau! Người đó chạy với vận tốc chậm hơn trong khoảng thời gian DÀI HƠN, "
            f"do đó trọng số thời gian cho vận tốc chậm lớn hơn, kéo vận tốc trung bình về phía thấp hơn trung bình cộng.\n\n"
            f"3. Công thức tính vận tốc trung bình chuẩn xác:\n"
            f"- Thời gian đi lượt đi: t1 = d / v1 = d / {v1}.\n"
            f"- Thời gian về lượt về: t2 = d / v2 = d / {v2}.\n"
            f"- Tổng thời gian cả đi và về: t_total = t1 + t2 = d * (1/{v1} + 1/{v2}) = d * ({v1} + {v2}) / ({v1} * {v2}).\n"
            f"- Vận tốc trung bình toàn chuyến:\n"
            f"  v_avg = S_total / t_total = (2d) / [d * ({v1} + {v2}) / ({v1} * {v2})]\n"
            f"  v_avg = (2 * v1 * v2) / (v1 + v2) (Trung bình điều hòa - Harmonic Mean).\n"
            f"- Thay số:\n"
            f"  v_avg = (2 * {v1} * {v2}) / ({v1} + {v2}) = {2 * v1 * v2} / {v1 + v2} = {v_harm:.2f} {unit}.\n"
            f"</think>"
        )

        answer = (
            f"Vận tốc trung bình trên toàn bộ chuyến đi cả đi và về là **{v_harm:.2f} {unit}** "
            f"(hoặc {v_harm:.1f} {unit} nếu làm tròn 1 chữ số thập phân).\n\n"
            f"*(Chú ý: Vận tốc trung bình là trung bình điều hòa 2*v1*v2/(v1+v2) = {v_harm:.2f} {unit}, "
            f"không phải là trung bình cộng ({v1}+{v2})/2 = {v_arith:.1f} {unit} do thời gian đi ở đoạn chậm dài hơn).* "
        )

        return {
            "category": "cognitive_traps_math",
            "difficulty": "medium",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }

    def _gen_palindrome_check(self) -> Dict[str, Any]:
        word, is_pal = self.rng.choice(self.PALINDROME_WORDS)
        chars = list(word.lower())
        n = len(chars)

        question = (
            f"Hãy kiểm tra xem từ \"{word}\" có phải là một từ đối xứng (palindrome) hay không. "
            f"Hãy phân tích và đối chiếu từng cặp ký tự đối xứng tương ứng."
        )

        step_lines = []
        is_symmetric = True
        mismatch_pair = None

        for i in range(n // 2):
            left_char = chars[i]
            right_char = chars[n - 1 - i]
            match = (left_char == right_char)
            if not match and is_symmetric:
                is_symmetric = False
                mismatch_pair = (i + 1, left_char, n - i, right_char)
            step_lines.append(
                f"- Cặp {i + 1}: Ký tự vị trí {i + 1} ('{left_char}') so với ký tự vị trí {n - i} ('{right_char}') -> "
                f"{'TRÙNG KHỚP' if match else 'KHÁC NHAU'}"
            )

        think = (
            f"<think>\n"
            f"1. Khái niệm Palindrome (Chuỗi đối xứng):\n"
            f"- Một từ/chuỗi là palindrome nếu khi đọc xuôi hay đọc ngược đều cho cùng một kết quả.\n"
            f"- Điều kiện toán học: S[i] == S[N - 1 - i] với mọi 0 <= i < N / 2.\n\n"
            f"2. Phân tích chuỗi \"{word}\":\n"
            f"- Chiều dài chuỗi: N = {n} ký tự.\n"
            f"- Bảng đối chiếu từng cặp đối xứng từ ngoài vào trong:\n"
            + "\n".join(step_lines) +
            f"\n\n3. Kết luận phân tích:\n"
        )

        if is_pal:
            think += (
                f"- Toàn bộ tất cả {n // 2} cặp ký tự đối xứng đều trùng khớp hoàn toàn.\n"
                f"- Do đó \"{word}\" là một từ đối xứng chuẩn xác (palindrome).\n"
                f"</think>"
            )
            answer = (
                f"Từ \"{word}\" **LÀ một từ đối xứng (palindrome)**.\n\n"
                f"*(Tất cả các cặp ký tự đối xứng từ hai phía vào giữa đều giống hệt nhau).* "
            )
        else:
            think += (
                f"- Xuất hiện sự bất đối xứng ở cặp: vị trí {mismatch_pair[0]} ('{mismatch_pair[1]}') khác vị trí {mismatch_pair[2]} ('{mismatch_pair[3]}').\n"
                f"- Do đó \"{word}\" KHÔNG PHẢI là từ đối xứng.\n"
                f"</think>"
            )
            answer = (
                f"Từ \"{word}\" **KHÔNG PHẢI là từ đối xứng (palindrome)**.\n\n"
                f"*(Lý do: Ký tự tại vị trí {mismatch_pair[0]} ('{mismatch_pair[1]}') không trùng khớp với ký tự đối xứng ở vị trí {mismatch_pair[2]} ('{mismatch_pair[3]}')).* "
            )

        return {
            "category": "cognitive_traps_math",
            "difficulty": "easy",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_VI},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{think}\n{answer}"}
            ]
        }


# ==============================================================================
# MAIN GENERATOR PIPELINE & CLI
# ==============================================================================
def format_chatml_text(messages: List[Dict[str, str]]) -> str:
    """Renders messages list to standard ChatML string."""
    text_parts = []
    for m in messages:
        role = m["role"]
        content = m["content"]
        text_parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    return "\n".join(text_parts)


def generate_dataset(
    num_samples: int = 1500,
    seed: int = 42,
    categories: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Generates a list of standardized CoT reasoning samples."""
    rng = random.Random(seed)

    lilypad_gen = LilypadExponentialGenerator(rng)
    letter_gen = LetterDecompositionGenerator(rng)
    logic_gen = KnightsAndKnavesGenerator(rng)
    cog_gen = CognitiveTrapMathGenerator(rng)

    generators = {
        "exponential_growth_lilypad": lilypad_gen,
        "character_decomposition_counting": letter_gen,
        "logic_truth_liar": logic_gen,
        "cognitive_traps_math": cog_gen
    }

    if categories:
        active_gens = {k: v for k, v in generators.items() if k in categories}
        if not active_gens:
            raise ValueError(f"No valid categories selected from: {categories}")
    else:
        active_gens = generators

    # Weights distribution:
    # exponential: ~30%, letter: ~25%, logic: ~25%, cognitive: ~20%
    weights = {
        "exponential_growth_lilypad": 0.30,
        "character_decomposition_counting": 0.25,
        "logic_truth_liar": 0.25,
        "cognitive_traps_math": 0.20
    }
    cat_keys = list(active_gens.keys())
    cat_weights = [weights.get(k, 0.25) for k in cat_keys]
    total_w = sum(cat_weights)
    cat_weights = [w / total_w for w in cat_weights]

    samples: List[Dict[str, Any]] = []

    for i in range(num_samples):
        chosen_cat = rng.choices(cat_keys, weights=cat_weights, k=1)[0]
        gen_instance = active_gens[chosen_cat]
        sample = gen_instance.generate()

        sample_id = f"cot_reasoning_{i+1:05d}"
        sample["id"] = sample_id

        # Verify think tags exist
        asst_msg = next((m for m in sample["messages"] if m["role"] == "assistant"), None)
        assert asst_msg is not None, f"Sample {sample_id} missing assistant message"
        assert "<think>" in asst_msg["content"] and "</think>" in asst_msg["content"], (
            f"Sample {sample_id} missing <think> tags in assistant response"
        )

        # Append ChatML text for unified compatibility with HF SFT / TRL / Unsloth
        sample["text"] = format_chatml_text(sample["messages"])
        samples.append(sample)

    return samples


def save_dataset_jsonl(samples: List[Dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")


def print_stats(samples: List[Dict[str, Any]]) -> None:
    cat_counts: Dict[str, int] = {}
    total_chars = 0
    total_think_chars = 0

    for s in samples:
        c = s.get("category", "unknown")
        cat_counts[c] = cat_counts.get(c, 0) + 1
        asst_content = next(m["content"] for m in s["messages"] if m["role"] == "assistant")
        total_chars += len(asst_content)
        if "<think>" in asst_content and "</think>" in asst_content:
            think_part = asst_content.split("</think>")[0].replace("<think>", "")
            total_think_chars += len(think_part)

    print("=" * 60)
    print("DATASET GENERATION STATISTICS")
    print("=" * 60)
    print(f"Total Samples Generated: {len(samples)}")
    print("\nCategory Distribution:")
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        pct = (count / len(samples)) * 100
        print(f"  - {cat:35s}: {count:5d} ({pct:5.1f}%)")

    avg_asst_len = total_chars / len(samples) if samples else 0
    avg_think_len = total_think_chars / len(samples) if samples else 0
    print(f"\nAverage Assistant Length: {avg_asst_len:.1f} characters")
    print(f"Average Thinking Length:  {avg_think_len:.1f} characters")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Synthetic Reasoning CoT Dataset Generator")
    parser.add_argument("--num-samples", type=int, default=1500, help="Number of samples to generate (default: 1500)")
    parser.add_argument("--output-path", type=str, default="data/training/reasoning_cot_train.jsonl", help="Output JSONL path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--categories", nargs="+", help="Specific categories to generate")
    parser.add_argument("--dry-run", action="store_true", help="Generate without writing to disk")

    args = parser.parse_args()

    out_file = Path(args.output_path).resolve()
    print(f"[*] Generating {args.num_samples} reasoning CoT samples (seed={args.seed})...")
    samples = generate_dataset(num_samples=args.num_samples, seed=args.seed, categories=args.categories)

    print_stats(samples)

    if not args.dry_run:
        save_dataset_jsonl(samples, out_file)
        file_size_mb = out_file.stat().st_size / (1024 * 1024)
        print(f"[+] Successfully exported {len(samples)} samples to: {out_file} ({file_size_mb:.2f} MB)")
    else:
        print("[*] Dry-run mode enabled: No file written.")


if __name__ == "__main__":
    main()
