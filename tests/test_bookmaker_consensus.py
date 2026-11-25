import unittest

from football_analysis.bookmaker_consensus import consensus, no_vig_probabilities


def market(home, draw, away, *, market="1x2", handicap=None, odds_field="odds"):
    return {
        "market": market,
        "handicap": handicap,
        "selections": [
            {"selection": "Home", odds_field: home},
            {"selection": "Draw", odds_field: draw},
            {"selection": "Away", odds_field: away},
        ],
    }


class BookmakerConsensusMigrationTests(unittest.TestCase):
    def test_no_vig_normalizes_and_accepts_reference_cote_field(self):
        probabilities = no_vig_probabilities({
            "selections": [
                {"selection": "Home", "cote": 2.0},
                {"selection": "Draw", "cote": 3.0},
                {"selection": "Away", "cote": 4.0},
            ]
        })
        self.assertAlmostEqual(sum(probabilities.values()), 1.0)
        self.assertAlmostEqual(probabilities["Home"], 6 / 13)

    def test_invalid_and_duplicate_market_outcomes_are_rejected(self):
        self.assertIsNone(no_vig_probabilities({"selections": [
            {"selection": "Home", "odds": 2.0},
            {"selection": "Home", "odds": 3.0},
        ]}))
        self.assertIsNone(no_vig_probabilities({"selections": [
            {"selection": "Home", "odds": float("nan")},
            {"selection": "Away", "odds": 2.0},
        ]}))
        self.assertIsNone(no_vig_probabilities({"selections": [{"selection": "Home", "odds": 1.0}]}))

    def test_weighted_consensus_and_reference_difference(self):
        books = {
            "Pinnacle": [market(1.8, 3.6, 4.2)],
            "Book A": [market(2.0, 3.5, 4.0)],
            "Book B": [market(2.1, 3.4, 3.8)],
            "1xBet": [market(2.2, 3.3, 3.6)],
        }
        result = consensus(books)
        home = result[("1x2", None, "Home")]
        self.assertEqual(home["bookmakers"], 4)
        self.assertIsNotNone(home["reference_probability"])
        self.assertAlmostEqual(home["probability"], sum(
            no_vig_probabilities(b[0])["Home"] * (3.0 if name == "Pinnacle" else 1.0)
            for name, b in books.items()
        ) / 6.0)
        self.assertAlmostEqual(home["difference_points"], round(
            (home["probability"] - home["reference_probability"]) * 100, 2))

    def test_exclusion_and_minimum_book_count(self):
        books = {
            "Pinnacle": [market(2.0, 3.0, 4.0)],
            "Book A": [market(2.1, 3.0, 3.8)],
            "Dafabet": [market(1.8, 3.5, 4.5)],
        }
        self.assertEqual(consensus(books), {})
        self.assertTrue(consensus(books, min_books=2))
        with self.assertRaises(ValueError):
            consensus(books, min_books=1)

    def test_repeated_market_from_same_book_does_not_inflate_book_count(self):
        books = {
            "Pinnacle": [market(2.0, 3.0, 4.0), market(1.9, 3.2, 4.1)],
            "Book A": [market(2.1, 3.0, 3.8)],
        }
        result = consensus(books, min_books=2)
        self.assertEqual(result[("1x2", None, "Home")]["bookmakers"], 2)


if __name__ == "__main__":
    unittest.main()
