#include "rakshak/models/ArtifactsModel.h"

ArtifactsModel::ArtifactsModel(QObject* parent) : QAbstractTableModel(parent) {}

int ArtifactsModel::rowCount(const QModelIndex&) const { return m_rows.size(); }
int ArtifactsModel::columnCount(const QModelIndex&) const { return 5; }

QVariant ArtifactsModel::data(const QModelIndex& idx, int role) const {
    if (!idx.isValid() || idx.row() < 0 || idx.row() >= m_rows.size()) return {};
    const auto& r = m_rows[idx.row()];
    if (role == Qt::DisplayRole) {
        switch (idx.column()) {
        case 0: return r.time;
        case 1: return r.caseId;
        case 2: return r.type;
        case 3: return r.sizeBytes;
        case 4: return r.tag;
        }
    }
    return {};
}

QVariant ArtifactsModel::headerData(int section, Qt::Orientation o, int role) const {
    if (o == Qt::Horizontal && role == Qt::DisplayRole) {
        switch (section) {
        case 0: return "Time";
        case 1: return "Case";
        case 2: return "Type";
        case 3: return "Size (B)";
        case 4: return "Tag";
        }
    }
    return {};
}