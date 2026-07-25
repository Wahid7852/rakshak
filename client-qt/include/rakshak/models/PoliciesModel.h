#pragma once
#include <QtGui/QStandardItemModel>

class PoliciesModel : public QStandardItemModel {
    Q_OBJECT
public:
    explicit PoliciesModel(QObject* parent = nullptr);
};