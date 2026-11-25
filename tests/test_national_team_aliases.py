import unittest

from football_analysis.team_names import normalize_team, similarity_score


class NationalTeamAliasTests(unittest.TestCase):
    def test_common_french_and_english_national_team_names_normalize_equally(self):
        pairs = [
            ("Côte d'Ivoire", "Ivory Coast"),
            ("Cameroun", "Cameroon"),
            ("Allemagne", "Germany"),
            ("Angleterre", "England"),
            ("Espagne", "Spain"),
            ("Pays-Bas", "Netherlands"),
            ("Afrique du Sud", "South Africa"),
            ("République démocratique du Congo", "DR Congo"),
            ("Türkiye", "Turkey"),
            ("Tchéquie", "Czechia"),
        ]
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                self.assertEqual(normalize_team(left), normalize_team(right))
                self.assertEqual(similarity_score(left, right), 100)


if __name__ == "__main__":
    unittest.main()
