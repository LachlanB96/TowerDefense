using UnityEngine;

public class GridManager : MonoBehaviour
{

    [SerializeField] private int _rows, _columns;
    [SerializeField] private Tile _tilePrefab;

    [SerializeField] private Transform _cam;


    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        GenerateGrid();
    }

    // Update is called once per frame
    void GenerateGrid()
    {
        for (int row = 0; row < _rows; row++)
        {
            for (int column = 0; column < _columns; column++)
            {
                Tile tile = Instantiate(_tilePrefab, new Vector3(column * 0.25f, 0, row * 0.25f), Quaternion.Euler(90, 0, 0), this.transform);
                tile.name = $"Tile {row} {column}";

                var isOffset = (row + column) % 2 == 1;
                tile.Init(isOffset);
            }
        }
        //_cam.transform.position = new Vector3((float)_columns / 2, (float)_rows / 2, -10f);
    }
}
