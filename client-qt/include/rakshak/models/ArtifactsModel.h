#pragma once
#include <QtCore/QObject>
#include <QtCore/QAbstractTableModel>
#include <QtWidgets/QMainWindow>
#include <QtCore/QVector>
#include <QtCore/QVariant>
#include <QtCore/QString>
#include <QtCore/QModelIndex>

struct ArtifactRow {
    QString time;
    QString caseId;
    QString type;
    int sizeBytes;
    QString tag;
};

class ArtifactsModel : public QAbstractTableModel {
    Q_OBJECT
public:
    explicit ArtifactsModel(QObject* parent = nullptr);
    int rowCount(const QModelIndex& parent = QModelIndex()) const;
    int columnCount(const QModelIndex& parent = QModelIndex()) const;
    QVariant data(const QModelIndex& index, int role = Qt::DisplayRole) const;
    QVariant headerData(int section, Qt::Orientation orientation, int role = Qt::DisplayRole) const;

private:
    QVector<ArtifactRow> m_rows;
};