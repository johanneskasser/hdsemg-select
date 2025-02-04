import unittest
from PyQt5.QtCore import Qt
from logic.channel_management import update_channel_status_single, select_all_channels, count_selected_channels

class TestChannelManagement(unittest.TestCase):

    def test_update_channel_status_single_checked(self):
        channel_status = [False, False, False]
        update_channel_status_single(channel_status, idx=1, state=Qt.Checked)
        self.assertTrue(channel_status[1])
        self.assertFalse(channel_status[0])
        self.assertFalse(channel_status[2])

    def test_update_channel_status_single_unchecked(self):
        channel_status = [True, True, True]
        update_channel_status_single(channel_status, idx=2, state=Qt.Unchecked)
        self.assertFalse(channel_status[2])
        self.assertTrue(channel_status[0])
        self.assertTrue(channel_status[1])

    def test_select_all_channels_select_true(self):
        channel_status = [False, False, False]
        updated_status = select_all_channels(channel_status, select=True)
        self.assertEqual(updated_status, [True, True, True])

    def test_select_all_channels_select_false(self):
        channel_status = [True, True, True]
        updated_status = select_all_channels(channel_status, select=False)
        self.assertEqual(updated_status, [False, False, False])

    def test_count_selected_channels(self):
        channel_status = [True, False, True, False, True]
        selected_count = count_selected_channels(channel_status)
        self.assertEqual(selected_count, 3)

    def test_count_selected_channels_no_selected(self):
        channel_status = [False, False, False]
        selected_count = count_selected_channels(channel_status)
        self.assertEqual(selected_count, 0)

    def test_count_selected_channels_all_selected(self):
        channel_status = [True, True, True]
        selected_count = count_selected_channels(channel_status)
        self.assertEqual(selected_count, 3)

if __name__ == "__main__":
    unittest.main()
