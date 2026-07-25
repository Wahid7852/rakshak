#pragma once
#include <QtCore/QByteArray>
#include <QtCore/QString>

namespace rakshak::common {

// Persists opaque UI layout blobs (QHeaderView::saveState(),
// QSplitter::saveState()) under a caller-chosen key - separate from
// SettingsData, which holds typed user-facing fields.
void saveUiState(const QString& key, const QByteArray& state);
QByteArray loadUiState(const QString& key);

} // namespace rakshak::common
