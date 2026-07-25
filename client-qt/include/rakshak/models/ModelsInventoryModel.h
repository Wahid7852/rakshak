#pragma once
#include <QtGui/QStandardItemModel>

class ModelsInventoryModel : public QStandardItemModel {
    Q_OBJECT
public:
    explicit ModelsInventoryModel(QObject* parent = nullptr);
};