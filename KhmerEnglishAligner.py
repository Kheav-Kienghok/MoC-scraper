from typing import Dict, List, Tuple, Set
import torch
from sentence_transformers import SentenceTransformer, util


class KhmerEnglishAligner:
    """
    A class to align Khmer sentences with English sentences using multilingual embeddings from LaBSE.

    The aligner performs a three-step process:
    1. Initial 1:1 matching between Khmer and English sentences
    2. Merging unused English sentences with existing pairs to improve alignment
    3. Returning aligned sentence pairs

    Attributes:
        model (SentenceTransformer): The multilingual sentence transformer model.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/LaBSE",
    ):
        """
        Initialize the KhmerEnglishAligner.

        Args:
            model_name (str): Name of the sentence transformer model to load. Defaults to LaBSE.
        """
        self.model = SentenceTransformer(model_name)

    def _encode_sentences(self, sentences: List[str]) -> torch.Tensor:
        """
        Encode sentences using the loaded model.

        Args:
            sentences (List[str]): List of sentences to encode.

        Returns:
            torch.Tensor: Encoded sentence embeddings.
        """
        return self.model.encode(sentences, convert_to_tensor=True)

    def _find_best_matches(
        self, english_embeddings: torch.Tensor, khmer_embeddings: torch.Tensor
    ) -> List[Tuple[int, int, float]]:
        """
        Find the best English match for each Khmer sentence.

        Args:
            english_embeddings (torch.Tensor): Encoded English sentence embeddings.
            khmer_embeddings (torch.Tensor): Encoded Khmer sentence embeddings.

        Returns:
            List[Tuple[int, int, float]]: List of (english_idx, khmer_idx, similarity_score) tuples.
        """
        pairs = []

        for km_idx, km_emb in enumerate(khmer_embeddings):
            # Compute similarities for all English sentences at once
            similarities = util.pytorch_cos_sim(
                english_embeddings, km_emb.unsqueeze(0)
            ).squeeze()
            best_en_idx = similarities.argmax().item()
            max_score = similarities[best_en_idx].item()

            pairs.append((best_en_idx, km_idx, max_score))

        return pairs

    def _merge_unused_sentences(
        self,
        pairs: List[Tuple[int, int, float]],
        english_sentences: List[str],
        khmer_embeddings: torch.Tensor,
        used_english_indices: Set[int],
    ) -> Tuple[List[str], List[Tuple[int, int, float]]]:
        """
        Merge unused English sentences into existing aligned pairs by selecting
        the best merge per pair based on score difference (positive or least negative).

        Args:
            pairs (List[Tuple[int, int, float]]): Initial sentence pairs.
            english_sentences (List[str]): Original English sentences.
            khmer_embeddings (torch.Tensor): Encoded Khmer sentence embeddings.
            used_english_indices (Set[int]): Set of already used English sentence indices.

        Returns:
            Tuple[List[str], List[Tuple[int, int, float]]]: Updated merged English texts and pairs.
        """
        merged_english_texts = [english_sentences[p[0]] for p in pairs]
        unused_english_indices = [
            i for i in range(len(english_sentences)) if i not in used_english_indices
        ]

        for pair_idx, (en_idx, km_idx, old_score) in enumerate(pairs):
            best_candidate = None
            best_diff = float("-inf")
            best_text = merged_english_texts[pair_idx]

            for unused_en_idx in unused_english_indices:
                candidate_text = (
                    f"{merged_english_texts[pair_idx]} {english_sentences[unused_en_idx]}"
                )
                merged_emb = self._encode_sentences([candidate_text])[0]
                km_emb = khmer_embeddings[km_idx]
                new_score = util.pytorch_cos_sim(merged_emb, km_emb).item()
                score_diff = new_score - old_score

                if score_diff > best_diff:
                    best_diff = score_diff
                    best_candidate = unused_en_idx
                    best_text = candidate_text
                    best_new_score = new_score

            if best_candidate is not None:
                merged_english_texts[pair_idx] = best_text
                pairs[pair_idx] = (en_idx, km_idx, best_new_score)
                used_english_indices.add(best_candidate)
                unused_english_indices.remove(best_candidate)

        return merged_english_texts, pairs

    def align(self, data: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        Align Khmer sentences to English sentences using semantic similarity.

        The method performs three steps:
        1. Encode all sentences using the multilingual model
        2. Find initial best matches between Khmer and English sentences
        3. Merge unused English sentences with existing pairs where beneficial

        Args:
            data (Dict[str, List[str]]): Dictionary with 'english' and 'khmer' sentence lists.
                Both lists should contain sentences as strings.

        Returns:
            Dict[str, List[str]]: Dictionary with aligned 'english' and 'khmer' sentence lists.
                The returned lists have the same length and corresponding indices represent aligned pairs.

        Raises:
            KeyError: If 'english' or 'khmer' keys are missing from data.
            ValueError: If input lists are empty.
        """
        if "english" not in data or "khmer" not in data:
            raise KeyError("Data must contain 'english' and 'khmer' keys")

        english_sentences = data["english"]
        khmer_sentences = data["khmer"]

        if not english_sentences or not khmer_sentences:
            raise ValueError("Input sentence lists cannot be empty")

        # Step 1: Encode sentences
        english_embeddings = self._encode_sentences(english_sentences)
        khmer_embeddings = self._encode_sentences(khmer_sentences)

        # Step 2: Find initial best matches
        pairs = self._find_best_matches(english_embeddings, khmer_embeddings)
        used_english_indices = {p[0] for p in pairs}

        # Step 3: Merge unused English sentences
        merged_english_texts, updated_pairs = self._merge_unused_sentences(
            pairs, english_sentences, khmer_embeddings, used_english_indices
        )

        # Return aligned results
        aligned_english = merged_english_texts
        aligned_khmer = [khmer_sentences[km_idx] for _, km_idx, _ in updated_pairs]

        return {"english": aligned_english, "khmer": aligned_khmer}


def main():

    data = {
        "english": [
            "(Geneva, Switzerland): On the morning of Tuesday, 28 January 2025, His Excellency SUON Prasith, Ambassador and Permanent Representative of the Permanent Mission of the Kingdom of Cambodia to the World Trade Organization and other international organizations (Economy and Trade) in Geneva, in his capacity as the outgoing Chair of the Group of 77 and China (Geneva Chapter), officially handed over the chairmanship to Mr. Cristóbal MELGAR PAZOS, Chargé d'Affaires of the Permanent Mission of Peru, for the 2025 mandate.",
            "The official handover ceremony was also attended by Mr. Pedro Manuel Moreno, Deputy Secretary-General of UNCTAD, representing Ms. Rebeca Grynspan, Secretary-General of UNCTAD, along with members of the Group of 77 and China.",
            "The Group of 77 and China is the largest negotiating group within the United Nations system, currently comprising 134 member countries. The Cambodian delegation assumed the duties of Vice-Chair of the Group of 77 and China (Geneva Chapter) on 23 November 2022 and took over the chairmanship on 30 January 2024. During its tenure, the Cambodian delegation represented the Group in approximately 95 meetings and negotiations, including facilitating the Group’s inputs into discussions at the United Nations in New York.",
            "Additionally, it led discussions and established three working groups: the Working Group on Digital Economy and Digitalization for Development, the Working Group on Financing for Development, and the Working Group on Climate Change, Trade, and Sustainable Development.",
            "Moreover, the Cambodian delegation successfully coordinated the 60th anniversary of the Group’s establishment on 13 September 2024, organizing high-level dialogues, adopting a joint ambassadorial statement, and issuing a press release. In preparation for the UNCTAD XVI Ministerial Conference scheduled for October 2025, Cambodia also led and coordinated internal discussions and negotiations to establish a common position for participation in the conference negotiations.",
            "On this occasion, the Deputy Secretary-General expressed his appreciation and recognition of the Cambodian delegation for its visionary leadership and commitment. He also reaffirmed his support for the Group in the upcoming Ministerial Conference negotiations and its dedication to upholding multilateralism for trade and development.",
            "In addition to the commitment of the incoming Chair from the Peruvian delegation, coordinators from various regional groups—including the Least Developed Countries (LDCs), the Asia-Pacific Group (APG), the Group of Latin American and Caribbean Countries (GRULAC), the Arab Group, and the Small Island Developing States (SIDS)—as well as many other member states, participated in the event. They delivered remarks praising and highly appreciating the Cambodian delegation’s leadership of the Group of 77 and China. Despite Cambodia's status as a least-developed country, it successfully led the Group to many remarkable achievements and outcomes during its term.",
        ],
        "khmer": [
            "(ហ្សឺណែវ, ស្វីស)៖ នាព្រឹកថ្ងៃអង្គារ ទី២៨ ខែមករា ឆ្នាំ២០២៥ ឯកឧត្តម សួន ប្រសិទ្ធ អគ្គរាជទូតនិងជាប្រធានស្ថាន នបេសកកម្មអចិន្ត្រៃយ៍កម្ពុជាប្រចាំអង្គការពាណិជ្ជកម្មពិភពលោក និងអង្គការអន្តរជាតិនានាពាក់ព័ន្ធនឹងវិស័យសេដ្ឋកិច ច្ច-ពាណិជ្ជកម្មប្រចាំទីក្រុងហ្សឺណែវ ប្រទេសស្វីស និងក្នុងនាមជាប្រធានចប់អាណត្តិរបស់ក្រុមប្រទេស G77 និងចិន បាន នផ្ទេរតួនាទីជាផ្លូវការជូន លោក Cristóbal MELGAR PAZOS ភារៈធារីស្ដីទីនៃស្ថានបេសកកម្មប៉េរូ ដើម្បីធ្វើជាប្រធានប បន្តពីកម្ពុជាសម្រាប់អាណត្តិឆ្នាំ២០២៥។ ពិធីផ្ទេរតួនាទីនេះ ក៏មានវត្តមានចូលរួមរបស់ លោក Pedro Manuel MORENO អគ គលេខាធិការរងសន្និសីទអង្គការសហប្រជាជាតិសម្រាប់ពាណិជ្ជកម្មនិងអភិវឌ្ឍន៍ (UNCTAD) និងជាតំណាងរបស់ លោកជំទាវ Rebe eca GRYNSPAN អគ្គលេខាធិការអង្គការ UNCTAD ព្រមទាំងសមាជិកក្រុមប្រទេស G77 និងចិន ផងដែរ។",
            "សូមជម្រាបជូនថា ក្រុ មប្រទេស G77 និងចិន គឺជាក្រុមចរចាធំជាងគេនៅក្នុងប្រព័ន្ធអង្គការសហប្រជាជាតិ និងដែលបច្ចុប្បន្នមានសមាជិកសរុប ១៣ ៣៤ ប្រទេស ក្នុងនោះគណៈប្រតិភូកម្ពុជាបានទទួលធ្វើជាអនុប្រធានក្រុមនេះចាប់តាំងពីថ្ងៃទី២៣ ខែវិច្ឆិកា ឆ្នាំ ២០២២ ន និងជាប្រធានចាប់តាំងពីថ្ងៃទី៣០ ខែមករា ឆ្នាំ២០២៤។ នៅក្នុងអាណត្តិជាប្រធាន គណៈប្រតិភូកម្ពុជាបានធ្វើជាតំណាងក្រុម មចូលរួមនៅក្នុងកិច្ចប្រជុំពិភាក្សានិងចរចា ក្រោមក្របខ័ណ្ឌអង្គការ UNCTAD សរុបប្រមាណ ៩៥លើក រួមទាំងការសម្របសម្រួ លផ្ដល់ធាតុចូលនានារបស់ក្រុមនេះទៅក្នុងកិច្ចពិភាក្សានៅទីក្រុងញូវយ៉ក ព្រមទាំងបានដឹកនាំការពិភាក្សានិងបង្កើតក្រុ មការងារចំនួន៣ គឺ ក្រុមការងារ ស្តីពីសេដ្ឋកិច្ចឌីជីថល និងឌីជីថលូបនីយកម្មសម្រាប់អភិវឌ្ឍន៍ ក្រុមការងារស្តីពីហិ រញ្ញប្បទានសម្រាប់អភិវឌ្ឍន៍ និងក្រុមការងារស្តីពីបម្រែបម្រួលអាកាសធាតុ ពាណិជ្ជកម្ម និងការអភិវឌ្ឍប្រកបដោយចីរភា ាព។",
            "បន្ថែមពីនេះ គណៈប្រតិភូកម្ពុជាបានសម្របសម្រួលរៀបចំខួបលើកទី ៦០ឆ្នាំ នៃការបង្កើតក្រុម G77 និងចិន កាលពីថ្ ងៃទី១៣ ខែកញ្ញា ឆ្នាំ២០២៤ ប្រកបដោយជោគជ័យនិងផ្លែផ្កា ដោយមានការរៀបចំវេទិកាកិច្ចសន្ទនាកម្រិតខ្ពស់ និងបានដាក់ចេ នៅនូវសេចក្តីថ្លែងការណ៍រួមកម្រិតអគ្គរាជ/រដ្ឋទូត និងសេចក្តីប្រកាសព័ត៌មានជាអាទិ៍ ព្រមទាំងបានដឹកនាំនិងសម្របសម្រ រួលកិច្ចពិភាក្សានិងចរចាផ្ទៃក្នុងសម្រាប់ស្វែងរកជំហររួម ដើម្បីជាមូលដ្ឋានគោលសម្រាប់ចូលរួមចរចានៅក្នុងកិច្ចប្រជុ ថ្នាក់រដ្ឋមន្ត្រីអង្គការUNCTADលើកទី១៦ ដែលគ្រោងប្រព្រឹត្តទៅនៅខែតុលា ឆ្នាំ២០២៥ ខាងមុខ។",
            "ក្នុងឱកាសនោះ លោកអ អគ្គលេខាធិការរង បានថ្លែងអំណរគុណ និងកោតសរសើរគណប្រតិភូកម្ពុជា ក្នុងការដឹកនាំក្រុមប្រទេស G77 និងចិនប្រកបដោយការ រទទួលខុសត្រូវ និងមានគោលដៅច្បាស់លាស់ ព្រមទាំងគូសបញ្ជាក់អំពីការបន្តគាំទ្រការចរចាសម្រាប់កិច្ចប្រជុំថ្នាក់រដ្ឋម មន្ត្រី និងលើកកម្ពស់ប្រព័ន្ធពហុភាគីនិយមសម្រាប់ពាណិជ្ជកម្ម និងអភិវឌ្ឍន៍ ផងដែរ។",
            "បន្ថែមលើការប្តេជ្ញាដឹកនាំក ក្រុមរបស់ប្រទេសប៉េរូប្រធានដឹកនាំថ្មី តំណាងក្រុមប្រទេស អភិវឌ្ឍន៍តិចតួច ក្រុមប្រទេសអាស៊ីប៉ាស៊ីហ្វិក ក្រុមប្រទ ទេសអាហ្វ្រិក ក្រុមប្រទេសអាម៉េរិកឡាទីន និងអាគារិក ក្រុមប្រទេស SIDS និងសមាជិករដ្ឋបំណុលផ្សេងទៀតបានចូលរួម ហើយ មានការផ្តល់សុន្ទរកថាសរសើរនិងកោតសរសើរចំពោះដឹកនាំក្រុមប្រទេស G77 និងចិនរបស់កម្ពុជាដែលទោះបីជាកម្ពុជាគឺជាប្រ រ្រទេសកំពុងអភិវឌ្ឍ តែបានដឹកនាំក្រុមប្រទេសនេះបានជោគជ័យមានលទ្ធផលយ៉ាងសំខាន់។",
        ],
    }

    aligner = KhmerEnglishAligner()
    result = aligner.align(data)

    for eng, kh in zip(result["english"], result["khmer"]):
        print(f"English: {eng}\nKhmer: {kh}\n")


if __name__ == "__main__":
    main()
